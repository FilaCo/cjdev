"""Creating a branch set: one checkout per project, all on one branch.

Every refusal happens in `decide`, before the first worktree exists, because
`git worktree add -b` creates the branch before it attempts the checkout and
leaves it behind when that fails. What is left is undone: a failed run takes
back the checkouts and branches it created, and nothing else.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto, unique
from pathlib import Path, PurePath
from typing import final

from cjdev.application.ports import Executor, FileSystem
from cjdev.application.runner import (
    Outcome,
    Runner,
    RunObserver,
    RunReport,
    UnitResult,
    Work,
)
from cjdev.application.workspace import held_projects
from cjdev.domain.branch import check_branch_name
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Manifest
from cjdev.errors import AbortedError, PreconditionError

DEFAULT_CHECKOUT_JOBS = 4
"""Bounded by the disk rather than by a remote: nothing here is online, and a
checkout writes a whole source tree."""


@final
@unique
class Action(Enum):
    """What this run has to do for one project. `PRESENT` is not work."""

    CREATE = auto()
    ADOPT = auto()
    PRESENT = auto()


@final
@dataclass(frozen=True)
class Probe:
    """What to ask one project's object store about."""

    project: str
    store: PurePath
    worktree: PurePath
    branch: str


@final
@dataclass(frozen=True)
class Held:
    """What that store answered."""

    project: str
    base: str | None
    """The ref recorded as this project's upstream default branch."""
    branch_exists: bool
    checked_out: str | None
    """The branch of the worktree already at this project's place in the set."""
    elsewhere: PurePath | None
    """Where this branch is checked out already, if somewhere else."""
    occupied: bool
    """The target path holds something git does not know about."""


@final
@dataclass(frozen=True)
class Observed:
    projects: tuple[Held, ...]
    directory_exists: bool
    """Undoing removes the branch-set directory only if this run made it."""


@final
@dataclass(frozen=True)
class Enrolment:
    project: str
    store: PurePath
    worktree: PurePath
    branch: str
    action: Action
    base: str | None = None
    """Where a created branch starts. None for an adopted one, which is taken
    where it stands."""


@final
@dataclass(frozen=True)
class BranchSetPlan:
    branch: str
    directory: PurePath
    enrolments: tuple[Enrolment, ...]
    directory_existed: bool

    @property
    def to_enrol(self) -> tuple[Enrolment, ...]:
        return tuple(e for e in self.enrolments if e.action is not Action.PRESENT)

    @property
    def is_noop(self) -> bool:
        return not self.to_enrol


@final
@dataclass(frozen=True)
class Enrolled:
    """One project's line in the report."""

    project: str
    worktree: PurePath
    action: Action
    outcome: Outcome
    error: Exception | None = None


@final
@dataclass(frozen=True)
class BranchSetReport:
    plan: BranchSetPlan
    rows: tuple[Enrolled, ...]
    interrupted: bool = False

    @property
    def ok(self) -> bool:
        return not self.interrupted and all(
            row.outcome is Outcome.DONE for row in self.rows
        )

    @property
    def failures(self) -> tuple[Enrolled, ...]:
        return tuple(row for row in self.rows if row.outcome is Outcome.FAILED)


Inspect = Callable[[Executor, Probe], Held]
Add = Callable[[Executor, Enrolment], None]
Drop = Callable[[Executor, Enrolment], None]


def decide(layout: WorkspaceLayout, branch: str, observed: Observed) -> BranchSetPlan:
    """The whole run, settled before any of it happens."""
    check_branch_name(branch)
    return BranchSetPlan(
        branch=branch,
        directory=layout.branch_set_dir(branch),
        enrolments=tuple(
            _enrolment(layout, branch, held) for held in observed.projects
        ),
        directory_existed=observed.directory_exists,
    )


def _enrolment(layout: WorkspaceLayout, branch: str, held: Held) -> Enrolment:
    worktree = layout.worktree(branch, held.project)
    action, base = _action(held, branch, worktree)
    return Enrolment(
        project=held.project,
        store=layout.object_store(held.project),
        worktree=worktree,
        branch=branch,
        action=action,
        base=base,
    )


def _action(held: Held, branch: str, worktree: PurePath) -> tuple[Action, str | None]:
    if held.checked_out == branch:
        return Action.PRESENT, None
    if held.checked_out is not None:
        # Flattening is one-way, so `fix/ice` and `fix-ice` want one directory.
        raise PreconditionError(
            f"{worktree} already holds branch set {held.checked_out}. "
            f"Two branch sets cannot share a directory.",
            subject=held.project,
        )
    if held.occupied:
        raise PreconditionError(
            f"{worktree} exists and is not empty; cjdev will not write into it.",
            subject=held.project,
        )
    if held.elsewhere is not None:
        raise PreconditionError(
            f"{branch} is already checked out at {held.elsewhere}. "
            f"git allows one worktree per branch.",
            subject=held.project,
        )
    if held.branch_exists:
        return Action.ADOPT, None
    if held.base is None:
        raise PreconditionError(
            f"{held.project} has no recorded upstream default branch to "
            f"start {branch} from.",
            subject=held.project,
            remedy="cjdev init",
        )
    return Action.CREATE, held.base


def report_rows(
    plan: BranchSetPlan, report: RunReport[Enrolment]
) -> tuple[Enrolled, ...]:
    """One row per project, in the plan's order rather than the finish order.

    Built from the plan: a project the set already covered ran no work and
    appears in no run report.
    """
    results = {result.label: result for result in report.results}
    rows = []
    for enrolment in plan.enrolments:
        result = results.get(enrolment.project)
        rows.append(
            Enrolled(
                project=enrolment.project,
                worktree=enrolment.worktree,
                action=enrolment.action,
                outcome=_outcome(enrolment, result),
                error=None if result is None else result.error,
            )
        )
    return tuple(rows)


def _outcome(enrolment: Enrolment, result: UnitResult[Enrolment] | None) -> Outcome:
    """Only `PRESENT` is done without having run; anything else missing from
    the report is a project the run never reached."""
    if result is not None:
        return result.outcome
    return Outcome.DONE if enrolment.action is Action.PRESENT else Outcome.CANCELLED


@final
class NewBranchSet:
    def __init__(
        self,
        manifest: Manifest,
        executor: Executor,
        file_system: FileSystem,
        inspect: Inspect,
        add: Add,
        drop: Drop,
    ) -> None:
        self._manifest = manifest
        self._executor = executor
        self._fs = file_system
        self._inspect = inspect
        self._add = add
        self._drop = drop

    def plan(
        self, root: Path, branch: str, *, jobs: int = DEFAULT_CHECKOUT_JOBS
    ) -> BranchSetPlan:
        """Everything `apply` would do, decided without doing any of it."""
        # Checked here as well as in `decide`, so that a name git would refuse
        # costs no git at all.
        check_branch_name(branch)
        layout = WorkspaceLayout(root)
        projects = held_projects(layout, self._manifest)
        if not projects:
            raise PreconditionError(
                f"{root} holds no projects, so there is nothing to branch.",
                remedy="cjdev init",
            )
        return decide(layout, branch, self._observe(layout, branch, projects, jobs))

    def perform(
        self,
        root: Path,
        branch: str,
        *,
        jobs: int = DEFAULT_CHECKOUT_JOBS,
        dry_run: bool = False,
        observer: RunObserver | None = None,
    ) -> BranchSetReport:
        return self.apply(
            self.plan(root, branch, jobs=jobs),
            jobs=jobs,
            dry_run=dry_run,
            observer=observer,
        )

    def apply(
        self,
        plan: BranchSetPlan,
        *,
        jobs: int = DEFAULT_CHECKOUT_JOBS,
        dry_run: bool = False,
        observer: RunObserver | None = None,
    ) -> BranchSetReport:
        # A dry run prints in sequential order: there is no work to overlap,
        # and its output would otherwise be at the mercy of the scheduler.
        report = Runner(1 if dry_run else jobs).run(
            [
                # Keyed by project: git does not serialise worktree and branch
                # operations on one object store for us.
                Work(key=e.project, label=e.project, action=self._adder(e))
                for e in plan.to_enrol
            ],
            observer=observer,
        )
        rows = report_rows(plan, report)
        # Nothing ran under a dry run, so there is nothing to take back.
        if not dry_run and not (report.ok and not report.interrupted):
            self._undo(plan, rows, jobs)
        return BranchSetReport(plan=plan, rows=rows, interrupted=report.interrupted)

    def _observe(
        self,
        layout: WorkspaceLayout,
        branch: str,
        projects: tuple[str, ...],
        jobs: int,
    ) -> Observed:
        report = Runner(jobs).run(
            [
                Work(
                    key=project,
                    label=project,
                    action=self._prober(layout, branch, project),
                )
                for project in projects
            ]
        )
        if report.interrupted:
            raise AbortedError("branch new")
        for result in report.results:
            # A store that cannot be read is not a project this run can decide
            # about, and deciding about the other five would build half a set.
            if result.error is not None:
                raise result.error
        return Observed(
            projects=tuple(r.value for r in report.results if r.value is not None),
            directory_exists=Path(layout.branch_set_dir(branch)).is_dir(),
        )

    def _prober(
        self, layout: WorkspaceLayout, branch: str, project: str
    ) -> Callable[[], Held]:
        probe = Probe(
            project=project,
            store=layout.object_store(project),
            worktree=layout.worktree(branch, project),
            branch=branch,
        )

        def look() -> Held:
            return self._inspect(self._executor, probe)

        return look

    def _adder(self, enrolment: Enrolment) -> Callable[[], Enrolment]:
        def add() -> Enrolment:
            self._add(self._executor, enrolment)
            return enrolment

        return add

    def _undo(self, plan: BranchSetPlan, rows: tuple[Enrolled, ...], jobs: int) -> None:
        """Take back what this run created, and only that.

        A failed unit is included because `worktree add -b` can leave the
        branch behind; a cancelled one never ran.
        """
        attempted = {
            row.project for row in rows if row.outcome in (Outcome.DONE, Outcome.FAILED)
        }
        # fail_fast=False: one project that cannot be taken back must not stop
        # the others from being.
        Runner(jobs, fail_fast=False).run(
            [
                Work(key=e.project, label=e.project, action=self._dropper(e))
                for e in plan.to_enrol
                if e.project in attempted
            ]
        )
        self._clear_directory(plan)

    def _dropper(self, enrolment: Enrolment) -> Callable[[], None]:
        def drop() -> None:
            self._drop(self._executor, enrolment)

        return drop

    def _clear_directory(self, plan: BranchSetPlan) -> None:
        """The empty directory `worktree add` made, if this run is what made
        it. Anything still inside belongs to somebody else."""
        if plan.directory_existed:
            return
        directory = Path(plan.directory)
        if directory.is_dir() and not any(directory.iterdir()):
            self._fs.remove(directory)
