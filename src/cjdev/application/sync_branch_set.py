"""`cjdev sync`: the branch set brought up to its projects' upstream.

Only a fast-forward is ever done. A branch with commits of its own that
upstream has moved past is reported with the command that would rebase it,
because which of rebase or merge is right is the author's call, and a silent
rebase rewrites what may already be pushed.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import final

from cjdev.application.ports import Executor
from cjdev.application.report_status import ManifestProvider
from cjdev.application.runner import (
    DEFAULT_NETWORK_JOBS,
    Outcome,
    Runner,
    RunObserver,
    Work,
)
from cjdev.application.workspace import enrolled_projects
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import AbortedError, PreconditionError


@final
@dataclass(frozen=True)
class Probe:
    project: str
    store: PurePath
    worktree: PurePath


@final
@dataclass(frozen=True)
class Drift:
    """One checkout against freshly fetched upstream."""

    project: str
    worktree: PurePath
    branch: str | None
    upstream: str | None
    """`upstream/<default branch>`, None when `init` recorded none."""
    ahead: int
    behind: int


@final
@dataclass(frozen=True)
class FastForward:
    project: str
    worktree: PurePath
    target: str
    commits: int


@final
@dataclass(frozen=True)
class Skip:
    project: str
    worktree: PurePath
    reason: str


@final
@dataclass(frozen=True)
class SyncPlan:
    steps: tuple[FastForward | Skip, ...]

    @property
    def to_move(self) -> tuple[FastForward, ...]:
        return tuple(step for step in self.steps if isinstance(step, FastForward))


@final
@dataclass(frozen=True)
class Synced:
    project: str
    outcome: Outcome | None
    """None for a project left where it is."""
    note: str
    error: Exception | None = None


@final
@dataclass(frozen=True)
class SyncReport:
    rows: tuple[Synced, ...]
    interrupted: bool = False

    @property
    def ok(self) -> bool:
        return not self.interrupted and all(
            row.outcome in (None, Outcome.DONE) for row in self.rows
        )


Inspect = Callable[[Executor, Probe], Drift]
"""Fetches `upstream` into the store first: the drift that matters is the
one against upstream as it is now."""
Move = Callable[[Executor, FastForward], None]


def decide(drifts: Sequence[Drift]) -> SyncPlan:
    return SyncPlan(steps=tuple(_step(d) for d in drifts))


def _step(d: Drift) -> FastForward | Skip:
    if d.upstream is None:
        raise PreconditionError(
            f"{d.project} has no recorded upstream default branch to sync with.",
            subject=d.project,
            remedy="cjdev init",
        )
    if d.branch is None:
        return Skip(d.project, d.worktree, "detached")
    if d.behind == 0:
        return Skip(d.project, d.worktree, "up to date")
    if d.ahead == 0:
        return FastForward(d.project, d.worktree, d.upstream, d.behind)
    return Skip(
        d.project,
        d.worktree,
        f"diverged: {d.ahead} ahead, {d.behind} behind {d.upstream}; "
        f"`git rebase {d.upstream}` in it",
    )


@final
class SyncBranchSet:
    def __init__(
        self,
        manifest: ManifestProvider,
        executor: Executor,
        inspect: Inspect,
        move: Move,
    ) -> None:
        self._manifest = manifest
        self._executor = executor
        self._inspect = inspect
        self._move = move

    def plan(
        self, root: Path, branch_set: str, *, observer: RunObserver | None = None
    ) -> SyncPlan:
        layout = WorkspaceLayout(root)
        probes = [
            Probe(
                project=project,
                store=layout.object_store(project),
                worktree=layout.worktree(branch_set, project),
            )
            for project in enrolled_projects(layout, self._manifest(), branch_set)
        ]
        report = Runner(DEFAULT_NETWORK_JOBS).run(
            [
                Work(key=p.project, label=p.project, action=self._prober(p))
                for p in probes
            ],
            observer=observer,
        )
        if report.interrupted:
            raise AbortedError("sync")
        for result in report.results:
            if result.error is not None:
                raise result.error
        return decide([r.value for r in report.results if r.value is not None])

    def apply(
        self,
        plan: SyncPlan,
        *,
        dry_run: bool = False,
        observer: RunObserver | None = None,
    ) -> SyncReport:
        report = Runner(1 if dry_run else DEFAULT_NETWORK_JOBS).run(
            [
                Work(key=s.project, label=s.project, action=self._mover(s))
                for s in plan.to_move
            ],
            observer=observer,
        )
        results = {result.label: result for result in report.results}
        rows = []
        for step in plan.steps:
            if isinstance(step, Skip):
                rows.append(Synced(step.project, None, step.reason))
                continue
            result = results.get(step.project)
            outcome = Outcome.CANCELLED if result is None else result.outcome
            rows.append(
                Synced(
                    step.project,
                    outcome,
                    f"fast-forwarded {step.commits} commit(s)"
                    if outcome is Outcome.DONE
                    else "",
                    error=None if result is None else result.error,
                )
            )
        return SyncReport(rows=tuple(rows), interrupted=report.interrupted)

    def _prober(self, probe: Probe) -> Callable[[], Drift]:
        return lambda: self._inspect(self._executor, probe)

    def _mover(self, step: FastForward) -> Callable[[], None]:
        return lambda: self._move(self._executor, step)
