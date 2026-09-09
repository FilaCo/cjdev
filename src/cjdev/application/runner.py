"""Fan-out: the one place in `cjdev` that runs work concurrently.

Commands hand this a list of independent units of work and get back a report.
They never spawn a thread themselves, so the job count, output ordering,
cancellation and the per-unit summary have one implementation each instead of
one per command.

Threads rather than processes: every unit of work is a subprocess wait, which
releases the GIL.
"""

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum, auto, unique
from typing import Generic, Protocol, TypeVar, final

from cjdev.errors import UsageError

T = TypeVar("T")

DEFAULT_NETWORK_JOBS = 4
"""Deliberately below the six-project fan-out: whether gitcode throttles
concurrent fetches from one account is unanswered, and the cost of guessing
high is being rate-limited mid-clone."""


class RunObserver(Protocol):
    """Watches a fan-out so that something can be shown while it runs.

    Both calls arrive on the worker's thread, which is what lets an observer
    attribute a unit's output to it without the runner having to know that
    output exists. Implementations must be safe to call concurrently.

    Deliberately not a port: this is a callback the caller passes to one
    method, not a collaborator the use case is built with.
    """

    def started(self, label: str) -> None: ...

    def finished(self, label: str, outcome: "Outcome") -> None: ...


@final
class SilentObserver:
    def started(self, label: str) -> None:
        pass

    def finished(self, label: str, outcome: "Outcome") -> None:
        pass


@final
@unique
class Outcome(Enum):
    DONE = auto()
    FAILED = auto()
    CANCELLED = auto()


@final
@dataclass(frozen=True)
class Work(Generic[T]):
    key: str
    """Two units of work sharing a key never run at the same time.

    For git operations the key is the project, because git does not serialise
    worktree, branch and fetch operations on one object store for us.
    """
    label: str
    action: Callable[[], T]


@final
@dataclass(frozen=True)
class UnitResult(Generic[T]):
    label: str
    outcome: Outcome
    value: T | None = None
    error: Exception | None = None


@final
@dataclass(frozen=True)
class RunReport(Generic[T]):
    results: tuple[UnitResult[T], ...]
    """In submission order, never completion order, so that the transcript and
    the exit code do not depend on scheduling."""
    interrupted: bool = False

    @property
    def ok(self) -> bool:
        return not self.interrupted and all(
            result.outcome is Outcome.DONE for result in self.results
        )

    def of(self, outcome: Outcome) -> tuple[UnitResult[T], ...]:
        return tuple(r for r in self.results if r.outcome is outcome)


@final
class Runner:
    def __init__(self, jobs: int = 1, *, fail_fast: bool = True) -> None:
        if jobs < 1:
            raise UsageError(f"jobs must be at least 1, got {jobs}.")
        self._jobs = jobs
        self._fail_fast = fail_fast

    def run(
        self, work: Sequence[Work[T]], observer: RunObserver | None = None
    ) -> RunReport[T]:
        if not work:
            return RunReport(())
        watcher = observer if observer is not None else SilentObserver()

        stop = threading.Event()
        locks = {item.key: threading.Lock() for item in work}

        def perform(item: Work[T]) -> UnitResult[T]:
            if stop.is_set():
                return _cancelled(item)
            with locks[item.key]:
                # Checked again inside the lock: a unit can wait here long
                # enough for an earlier failure to make its work pointless.
                if stop.is_set():
                    return _cancelled(item)
                watcher.started(item.label)
                try:
                    result = UnitResult(item.label, Outcome.DONE, value=item.action())
                except Exception as exc:
                    if self._fail_fast:
                        stop.set()
                    result = UnitResult(item.label, Outcome.FAILED, error=exc)
                watcher.finished(item.label, result.outcome)
                return result

        def _cancelled(item: Work[T]) -> UnitResult[T]:
            watcher.finished(item.label, Outcome.CANCELLED)
            return UnitResult(item.label, Outcome.CANCELLED)

        results: list[UnitResult[T] | None] = [None] * len(work)
        interrupted = False

        with ThreadPoolExecutor(
            max_workers=self._jobs, thread_name_prefix="cjdev"
        ) as pool:
            futures = [pool.submit(perform, item) for item in work]
            try:
                for index, future in enumerate(futures):
                    results[index] = future.result()
            except KeyboardInterrupt:
                # Pending work is dropped, in-flight work is left to finish
                # rather than killed mid-write; leaving the pool's context
                # manager is what waits for it.
                interrupted = True
                stop.set()
                for future in futures:
                    future.cancel()

        for index, (item, future) in enumerate(zip(work, futures, strict=True)):
            if results[index] is None:
                results[index] = (
                    future.result()
                    if future.done() and not future.cancelled()
                    else UnitResult(item.label, Outcome.CANCELLED)
                )

        return RunReport(
            tuple(r for r in results if r is not None), interrupted=interrupted
        )
