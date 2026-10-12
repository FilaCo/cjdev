"""Committing one change across the projects of a branch set.

One message for every project that has something to commit, because a change
that spans the compiler and its tests is one change. Every refusal is in
`decide`: a set committed in half its projects is the state this command
exists to prevent.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import final

from cjdev.application.ports import Executor
from cjdev.application.report_status import ManifestProvider
from cjdev.application.runner import Outcome, Runner, RunObserver, Work
from cjdev.application.workspace import enrolled_projects
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import AbortedError, PreconditionError, UsageError

DEFAULT_COMMIT_JOBS = 4


@final
@dataclass(frozen=True)
class Probe:
    project: str
    store: PurePath
    worktree: PurePath
    everything: bool
    """`--all`: tracked changes count, not only staged ones."""


@final
@dataclass(frozen=True)
class Pending:
    """What one checkout holds."""

    project: str
    worktree: PurePath
    branch: str | None
    default_branch: str | None
    changes: bool


@final
@dataclass(frozen=True)
class Message:
    text: str
    everything: bool
    signoff: bool


@final
@dataclass(frozen=True)
class CommitPlan:
    projects: tuple[Pending, ...]
    """Every checkout the run covers, in manifest order."""

    @property
    def to_commit(self) -> tuple[Pending, ...]:
        return tuple(p for p in self.projects if p.changes)


@final
@dataclass(frozen=True)
class Committed:
    project: str
    worktree: PurePath
    outcome: Outcome | None
    """None for a project with nothing to commit: skipped, not run."""
    head: str | None = None
    error: Exception | None = None


@final
@dataclass(frozen=True)
class CommitReport:
    rows: tuple[Committed, ...]
    interrupted: bool = False

    @property
    def ok(self) -> bool:
        return not self.interrupted and all(
            row.outcome in (None, Outcome.DONE) for row in self.rows
        )


Inspect = Callable[[Executor, Probe], Pending]
Commit = Callable[[Executor, PurePath, Message], str]


def decide(pending: Sequence[Pending], only: Sequence[str] = ()) -> CommitPlan:
    known = {p.project for p in pending}
    unknown = sorted(set(only) - known)
    if unknown:
        raise UsageError(
            f"{', '.join(unknown)}: not checked out in this branch set. "
            f"Checked out: {', '.join(p.project for p in pending)}."
        )
    chosen = tuple(p for p in pending if not only or p.project in only)
    for project in chosen:
        if project.changes:
            _refuse_branch(project.project, project.branch, project.default_branch)
    return CommitPlan(projects=chosen)


def _refuse_branch(project: str, branch: str | None, default: str | None) -> None:
    if branch is None:
        raise PreconditionError(
            f"{project} is detached, so a commit would belong to no branch.",
            subject=project,
        )
    if branch == default:
        # Upstream is changed through PRs from a branch, and a commit on the
        # default branch is one the next sync has to throw away.
        raise PreconditionError(
            f"{project} is on its default branch {branch}.",
            subject=project,
            remedy="cjdev branch new <branch set>",
        )


@final
class CommitBranchSet:
    def __init__(
        self,
        manifest: ManifestProvider,
        executor: Executor,
        inspect: Inspect,
        commit: Commit,
    ) -> None:
        self._manifest = manifest
        self._executor = executor
        self._inspect = inspect
        self._commit = commit

    def plan(
        self,
        root: Path,
        branch_set: str,
        *,
        everything: bool = False,
        only: Sequence[str] = (),
        observer: RunObserver | None = None,
    ) -> CommitPlan:
        layout = WorkspaceLayout(root)
        probes = [
            Probe(
                project=project,
                store=layout.object_store(project),
                worktree=layout.worktree(branch_set, project),
                everything=everything,
            )
            for project in enrolled_projects(layout, self._manifest(), branch_set)
        ]
        report = Runner(DEFAULT_COMMIT_JOBS).run(
            [
                Work(key=p.project, label=p.project, action=self._prober(p))
                for p in probes
            ],
            observer=observer,
        )
        if report.interrupted:
            raise AbortedError("commit")
        for result in report.results:
            if result.error is not None:
                raise result.error
        return decide([r.value for r in report.results if r.value is not None], only)

    def apply(
        self,
        plan: CommitPlan,
        message: Message,
        *,
        dry_run: bool = False,
        observer: RunObserver | None = None,
    ) -> CommitReport:
        if not message.text.strip():
            raise UsageError("the commit message is empty.")
        report = Runner(1 if dry_run else DEFAULT_COMMIT_JOBS).run(
            [
                Work(key=p.project, label=p.project, action=self._committer(p, message))
                for p in plan.to_commit
            ],
            observer=observer,
        )
        results = {result.label: result for result in report.results}
        rows = []
        for project in plan.projects:
            result = results.get(project.project)
            if not project.changes:
                rows.append(Committed(project.project, project.worktree, None))
            elif result is None:
                rows.append(
                    Committed(project.project, project.worktree, Outcome.CANCELLED)
                )
            else:
                rows.append(
                    Committed(
                        project.project,
                        project.worktree,
                        result.outcome,
                        # A dry run committed nothing, so the HEAD read back
                        # is the old one and would read as the new commit.
                        head=None if dry_run else result.value,
                        error=result.error,
                    )
                )
        return CommitReport(rows=tuple(rows), interrupted=report.interrupted)

    def _prober(self, probe: Probe) -> Callable[[], Pending]:
        return lambda: self._inspect(self._executor, probe)

    def _committer(self, pending: Pending, message: Message) -> Callable[[], str]:
        return lambda: self._commit(self._executor, pending.worktree, message)
