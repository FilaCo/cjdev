"""Showing a fan-out while it runs, and capturing what it prints.

Three questions get asked of a command that takes minutes - what is it doing,
how long has it been doing it, and how much longer - so the display answers
all three rather than only spinning. The per-unit step comes from the command
currently running in that unit; the estimate comes from the units that have
already finished, and appears only once there is one to average.
"""

import threading
import time
from collections.abc import Sequence
from types import TracebackType
from typing import final

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from cjdev.application.runner import Outcome

from ._console import DETAIL, MARKS, RUNNING, WAITING

LIVE_AFTER = 0.4
"""How long a run has to last before its display is worth drawing.

A local checkout is often over in a tenth of a second, and a table that
appears and is taken away again in that time is harder to read than the report
printed after it. Long enough to skip those, short enough that a run somebody
is actually waiting on still answers "is it doing anything".
"""


def format_duration(seconds: float) -> str:
    """`8.4s` below a minute, `2m 05s` above it.

    Seconds keep a decimal only while they are the whole answer; once minutes
    are on screen the tenth of a second is noise.
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes}m {rest:02d}s"


@final
class ConsoleProgress:
    def __init__(
        self,
        console: Console,
        fallback: Console | None = None,
        *,
        delay: float = 0.0,
        transient: bool = False,
    ) -> None:
        self._console = console
        self._fallback = fallback
        """Where the plain per-unit lines go when there is no terminal to
        animate. Separate from `console` so that a CI log still sees movement
        while stdout stays the ordered report something might be parsing."""
        self._delay = delay
        """How long to wait before drawing anything. Zero draws at once, for a
        command whose first unit of work is a fetch and which would otherwise
        show nothing at all for a minute."""
        self._transient = transient
        """Whether the display is taken away when the run ends. For a command
        that prints its own table afterwards it has to be, or the same run is
        reported twice in two shapes."""
        self._title = ""
        self._jobs = 1
        self._labels: tuple[str, ...] = ()
        self._done: dict[str, Outcome] = {}
        self._started_at: dict[str, float] = {}
        self._took: dict[str, float] = {}
        self._step: dict[str, str] = {}
        self._lines: dict[str, list[str]] = {}
        self._owner = threading.local()
        self._guard = threading.Lock()
        self._display = threading.Lock()
        """Held while the live display is started or stopped, and never while
        it renders: `Live.start()` draws a frame, and a frame reads `_guard`."""
        self._live: Live | None = None
        self._timer: threading.Timer | None = None
        self._animating = False
        self._closed = False
        self._began_at: float | None = None
        self._spinner = Spinner("dots", style=RUNNING)

    def track(self, labels: Sequence[str], *, title: str = "", jobs: int = 1) -> None:
        """The rows to show, in the order they must always appear.

        `jobs` is not decoration: the estimate divides the remaining work by
        how much of it can be in flight at once, and sequentially that is a
        very different number.
        """
        self._labels = tuple(labels)
        self._title = title
        self._jobs = max(1, jobs)

    def __rich__(self) -> Table:
        """Rendered on every refresh rather than only when something changes.

        `Live` re-renders whatever it was handed, so handing it `self` is what
        makes the elapsed times and the estimate count up between events. A
        table built once would freeze at whatever the last event left behind -
        which, during a five-minute fetch, is `0.0s`.
        """
        return self._render()

    def __enter__(self) -> "ConsoleProgress":
        self._began_at = time.monotonic()
        # A pipe or a CI log gets one line per unit instead: an animation
        # redrawn 8 times a second is control codes once nobody is watching.
        self._animating = self._console.is_terminal and bool(self._labels)
        if not self._animating:
            return self
        if self._delay <= 0:
            self._draw()
        else:
            # A thread rather than a check on the next event: a run with one
            # long unit produces no events at all to hang the check on.
            self._timer = threading.Timer(self._delay, self._draw)
            self._timer.daemon = True
            self._timer.start()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        with self._display:
            self._closed = True
            live, self._live = self._live, None
        if live is not None:
            live.stop()

    def _draw(self) -> None:
        """Start the display, unless the run ended while waiting to."""
        with self._display:
            if self._closed or self._live is not None:
                return
            self._live = Live(
                self,
                console=self._console,
                refresh_per_second=8,
                transient=self._transient,
            )
            self._live.start()

    def started(self, label: str) -> None:
        self._owner.label = label
        with self._guard:
            self._started_at[label] = time.monotonic()
            self._step[label] = "starting"

    def step(self, what: str) -> None:
        """What the unit running on this thread is doing right now.

        Bound to the thread rather than passed a label, because it is called
        from deep inside `infra/` by code that knows the command it is about
        to run and nothing about the fan-out around it.
        """
        label = getattr(self._owner, "label", None)
        if label is None:
            return
        with self._guard:
            self._step[label] = what

    def finished(self, label: str, outcome: Outcome) -> None:
        with self._guard:
            self._done[label] = outcome
            self._step.pop(label, None)
            if label in self._started_at:
                self._took[label] = time.monotonic() - self._started_at.pop(label)
        self._report_plainly(label, outcome)

    def emit(self, line: str) -> None:
        """Buffered, never printed: a worker writing straight to the terminal
        would both corrupt the live display and let scheduling decide the
        order of the transcript."""
        label = getattr(self._owner, "label", None)
        with self._guard:
            self._lines.setdefault(label or "", []).append(line)

    def lines(self, label: str = "") -> tuple[str, ...]:
        """What one unit printed. The empty label is the command itself -
        whatever was emitted before any unit of work started."""
        return tuple(self._lines.get(label, ()))

    def elapsed(self) -> float:
        return 0.0 if self._began_at is None else time.monotonic() - self._began_at

    def summary(self) -> str:
        """One line for after the display is gone, and for when there was
        never one: `3 done, 1 failed in 1m 12s`."""
        counted = {
            "done": sum(1 for o in self._done.values() if o is Outcome.DONE),
            "failed": sum(1 for o in self._done.values() if o is Outcome.FAILED),
            "cancelled": sum(1 for o in self._done.values() if o is Outcome.CANCELLED),
        }
        parts = [f"{count} {name}" for name, count in counted.items() if count]
        happened = ", ".join(parts) or "nothing to do"
        return f"{happened} in {format_duration(self.elapsed())}"

    def _report_plainly(self, label: str, outcome: Outcome) -> None:
        # `_animating` rather than "is the display up": while it is waiting out
        # its delay it is not, and a unit finishing in that window would
        # otherwise print a line the display is about to draw over.
        if self._animating or self._fallback is None or not self._labels:
            return
        mark, style = MARKS[outcome]
        took = self._took.get(label)
        suffix = f"  {format_duration(took)}" if took is not None else ""
        self._fallback.print(
            Text(f"{mark} ", style=style).append(
                f"[{len(self._done)}/{len(self._labels)}] {label}{suffix}", style=DETAIL
            ),
            highlight=False,
            soft_wrap=True,
        )

    def _render(self) -> Table:
        outer = Table.grid()
        with self._guard:
            outer.add_row(Text(self._headline(), style=DETAIL))
            outer.add_row(self._rows())
        return outer

    def _headline(self) -> str:
        """Counts, elapsed and an estimate, all of the run rather than a unit.

        The estimate is prefixed `~` and omitted entirely until a unit has
        finished, because an estimate with no sample behind it is a number
        made up to fill a column.
        """
        parts = [self._title] if self._title else []
        parts.append(f"{len(self._done)}/{len(self._labels)} done")
        parts.append(f"{format_duration(self.elapsed())} elapsed")
        remaining = self._remaining()
        if remaining is not None:
            parts.append(f"~{format_duration(remaining)} left")
        return "  ·  ".join(parts)

    def _remaining(self) -> float | None:
        finished = [self._took[label] for label in self._took]
        if not finished:
            return None
        typical = sum(finished) / len(finished)
        now = time.monotonic()
        outstanding = [
            # A unit already running has served part of its time; one that has
            # not started owes the whole of it. A unit running longer than
            # typical owes nothing more that we can justify guessing at.
            max(typical - (now - self._started_at[label]), 0.0)
            if label in self._started_at
            else typical
            for label in self._labels
            if label not in self._done
        ]
        if not outstanding:
            return None
        remaining = sum(outstanding) / min(self._jobs, len(outstanding))
        # A unit that has already outrun the average owes an unknown amount,
        # not zero. Saying "~0.0s left" while the spinner keeps turning is
        # worse than saying nothing, so below a second the estimate goes away.
        return remaining if remaining >= 1.0 else None

    def _rows(self) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(width=2)
        table.add_column(ratio=1)
        table.add_column(style=DETAIL)
        table.add_column(justify="right", style=DETAIL)

        now = time.monotonic()
        for label in self._labels:
            outcome = self._done.get(label)
            if outcome is not None:
                mark, style = MARKS[outcome]
                table.add_row(
                    Text(mark, style=style),
                    label,
                    "",
                    self._took_text(label),
                )
            elif label in self._started_at:
                table.add_row(
                    self._spinner,
                    label,
                    self._step.get(label, ""),
                    format_duration(now - self._started_at[label]),
                )
            else:
                mark, style = WAITING
                table.add_row(
                    Text(mark, style=style), Text(label, style=style), "queued", ""
                )
        return table

    def _took_text(self, label: str) -> str:
        took = self._took.get(label)
        return format_duration(took) if took is not None else ""
