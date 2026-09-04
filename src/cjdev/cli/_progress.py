"""Showing a fan-out while it runs, and capturing what it prints."""

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


@final
class ConsoleProgress:
    def __init__(self, console: Console) -> None:
        self._console = console
        self._labels: tuple[str, ...] = ()
        self._done: dict[str, Outcome] = {}
        self._started_at: dict[str, float] = {}
        self._took: dict[str, float] = {}
        self._lines: dict[str, list[str]] = {}
        self._owner = threading.local()
        self._guard = threading.Lock()
        self._live: Live | None = None
        self._spinner = Spinner("dots", style=RUNNING)

    def track(self, labels: Sequence[str]) -> None:
        """The rows to show, in the order they must always appear."""
        self._labels = tuple(labels)

    def __enter__(self) -> "ConsoleProgress":
        # A pipe or a CI log gets the summary and nothing else: an animation
        # redrawn 12 times a second is noise once it is not being watched.
        if self._console.is_terminal and self._labels:
            self._live = Live(
                self._render(), console=self._console, refresh_per_second=12
            )
            self._live.__enter__()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        if self._live is not None:
            self._live.update(self._render())
            self._live.__exit__(kind, value, trace)
            self._live = None

    def started(self, label: str) -> None:
        self._owner.label = label
        with self._guard:
            self._started_at[label] = time.monotonic()
        self._refresh()

    def finished(self, label: str, outcome: Outcome) -> None:
        with self._guard:
            self._done[label] = outcome
            if label in self._started_at:
                self._took[label] = time.monotonic() - self._started_at.pop(label)
        self._refresh()

    def emit(self, line: str) -> None:
        """Buffered, never printed: a worker writing straight to the terminal
        would both corrupt the live display and let scheduling decide the
        order of the transcript."""
        label = getattr(self._owner, "label", None)
        with self._guard:
            self._lines.setdefault(label or "", []).append(line)

    def lines(self, label: str) -> tuple[str, ...]:
        return tuple(self._lines.get(label, ()))

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render())

    def _render(self) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(width=2)
        table.add_column(ratio=1)
        table.add_column(justify="right", style=DETAIL)

        with self._guard:
            for label in self._labels:
                outcome = self._done.get(label)
                if outcome is not None:
                    mark, style = MARKS[outcome]
                    table.add_row(
                        Text(mark, style=style), label, self._took_text(label)
                    )
                elif label in self._started_at:
                    table.add_row(self._spinner, label, "")
                else:
                    mark, style = WAITING
                    table.add_row(Text(mark, style=style), Text(label, style=style), "")
        return table

    def _took_text(self, label: str) -> str:
        took = self._took.get(label)
        return f"{took:.1f}s" if took is not None else ""
