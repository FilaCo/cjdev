"""Pointing every project's `origin` at the user's fork.

The URL is derived from the project's own `upstream` and the workspace's fork
owner (ADR-0043), so nothing per project is typed. An `origin` that is already
there and points elsewhere is the user's, and is reported rather than
overwritten: a fork named differently is a reason, not a mistake.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum, auto, unique
from pathlib import Path, PurePath
from typing import final

from cjdev.application.ports import Executor, FileSystem
from cjdev.application.report_status import ManifestProvider
from cjdev.application.runner import Outcome, Runner, RunObserver, Work
from cjdev.application.workspace import held_projects
from cjdev.domain.fork import check_fork_owner, fork_url
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import AbortedError, PreconditionError

DEFAULT_WIRING_JOBS = 4


@final
@dataclass(frozen=True)
class Remotes:
    project: str
    store: PurePath
    upstream: str | None
    origin: str | None


@final
@unique
class Wiring(Enum):
    ADD = auto()
    PRESENT = auto()
    DISAGREES = auto()


@final
@dataclass(frozen=True)
class Wire:
    project: str
    store: PurePath
    url: str
    wiring: Wiring
    existing: str | None = None


@final
@dataclass(frozen=True)
class Wired:
    wire: Wire
    outcome: Outcome | None
    """None where nothing ran: present, or disagreeing."""
    error: Exception | None = None


@final
@dataclass(frozen=True)
class OriginReport:
    owner: str
    rows: tuple[Wired, ...]
    interrupted: bool = False

    @property
    def ok(self) -> bool:
        return not self.interrupted and all(
            row.outcome in (None, Outcome.DONE) for row in self.rows
        )


ReadRemotes = Callable[[Executor, PurePath, str], Remotes]
AddOrigin = Callable[[Executor, PurePath, str], None]
ReadOwner = Callable[[Path], str | None]
RecordOwner = Callable[[FileSystem, Path, str], None]


def decide(owner: str, remotes: Sequence[Remotes]) -> tuple[Wire, ...]:
    return tuple(_wire(owner, r) for r in remotes)


def _wire(owner: str, remotes: Remotes) -> Wire:
    if remotes.upstream is None:
        raise PreconditionError(
            f"{remotes.project} has no upstream to derive its fork from.",
            subject=remotes.project,
        )
    url = fork_url(remotes.upstream, owner)
    if remotes.origin is None:
        return Wire(remotes.project, remotes.store, url, Wiring.ADD)
    if remotes.origin == url:
        return Wire(remotes.project, remotes.store, url, Wiring.PRESENT)
    return Wire(
        remotes.project, remotes.store, url, Wiring.DISAGREES, existing=remotes.origin
    )


@final
class WireOrigin:
    def __init__(
        self,
        manifest: ManifestProvider,
        executor: Executor,
        file_system: FileSystem,
        read_remotes: ReadRemotes,
        add_origin: AddOrigin,
        read_owner: ReadOwner,
        record_owner: RecordOwner,
    ) -> None:
        self._manifest = manifest
        self._executor = executor
        self._fs = file_system
        self._read_remotes = read_remotes
        self._add_origin = add_origin
        self._read_owner = read_owner
        self._record_owner = record_owner

    def owner(self, root: Path, given: str | None = None) -> str | None:
        """`given` if there is one, else what the workspace recorded."""
        return check_fork_owner(given) if given else self._read_owner(root)

    def perform(
        self,
        root: Path,
        owner: str | None = None,
        *,
        observer: RunObserver | None = None,
    ) -> OriginReport:
        """`owner`, when given, is recorded first: it is the setting the
        caller asked for, and a project that then fails to wire is retried
        by running this again without it."""
        resolved = self.owner(root, owner)
        if resolved is None:
            raise PreconditionError(
                f"{root} names no fork owner, so there is no fork to point origin at.",
                remedy="cjdev config origin <fork owner>",
            )
        layout = WorkspaceLayout(root)
        projects = held_projects(layout, self._manifest())
        readings = Runner(DEFAULT_WIRING_JOBS).run(
            [
                Work(key=p, label=p, action=self._reader(layout.object_store(p), p))
                for p in projects
            ],
        )
        if readings.interrupted:
            raise AbortedError("origin")
        for result in readings.results:
            if result.error is not None:
                raise result.error
        wires = decide(
            resolved, [r.value for r in readings.results if r.value is not None]
        )
        if owner:
            self._record_owner(self._fs, root, resolved)

        report = Runner(DEFAULT_WIRING_JOBS, fail_fast=False).run(
            [
                Work(key=w.project, label=w.project, action=self._adder(w))
                for w in wires
                if w.wiring is Wiring.ADD
            ],
            observer=observer,
        )
        results = {result.label: result for result in report.results}
        rows = []
        for wire in wires:
            result = results.get(wire.project)
            if wire.wiring is not Wiring.ADD:
                rows.append(Wired(wire, None))
            elif result is None:
                rows.append(Wired(wire, Outcome.CANCELLED))
            else:
                rows.append(Wired(wire, result.outcome, result.error))
        return OriginReport(
            owner=resolved, rows=tuple(rows), interrupted=report.interrupted
        )

    def _reader(self, store: PurePath, project: str) -> Callable[[], Remotes]:
        return lambda: self._read_remotes(self._executor, store, project)

    def _adder(self, wire: Wire) -> Callable[[], None]:
        return lambda: self._add_origin(self._executor, wire.store, wire.url)
