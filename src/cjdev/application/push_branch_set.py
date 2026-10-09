"""Pushing a branch set's branch to `origin`, the user's fork, per project.

Never to `upstream`: it is read-only by design, and the only remote this
command names is `origin`. A rewritten history goes out only with
`--force-with-lease`, and then with the lease pinned to what this run saw, so
a push from elsewhere in between is refused rather than overwritten.
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
from cjdev.domain.fork import web_page
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
class Unpushed:
    """What one checkout holds against its fork."""

    project: str
    worktree: PurePath
    branch: str | None
    default_branch: str | None
    upstream_url: str | None
    origin_url: str | None
    origin_head: str | None
    """`origin`'s copy of the branch as last seen, or None if it has none."""
    ahead: int
    """Commits origin's copy lacks - or, with no copy, upstream's default
    branch lacks: a branch with no commits of its own is not worth a push."""
    behind: int
    """Commits origin's copy has that the branch does not: a rewrite."""
    tracked: bool


@final
@dataclass(frozen=True)
class Push:
    project: str
    worktree: PurePath
    branch: str
    origin_url: str
    set_upstream: bool
    lease: str | None
    """The SHA origin must still hold, "" for "must not exist", or None for
    a plain push."""


@final
@dataclass(frozen=True)
class Skip:
    project: str
    worktree: PurePath
    reason: str


@final
@dataclass(frozen=True)
class PushPlan:
    steps: tuple[Push | Skip, ...]

    @property
    def to_push(self) -> tuple[Push, ...]:
        return tuple(step for step in self.steps if isinstance(step, Push))


@final
@dataclass(frozen=True)
class Pushed:
    project: str
    worktree: PurePath
    outcome: Outcome | None
    """None for a project skipped as having nothing to push."""
    note: str = ""
    """Why it was skipped, or where to open the PR."""
    error: Exception | None = None


@final
@dataclass(frozen=True)
class PushReport:
    rows: tuple[Pushed, ...]
    interrupted: bool = False

    @property
    def ok(self) -> bool:
        return not self.interrupted and all(
            row.outcome in (None, Outcome.DONE) for row in self.rows
        )


Inspect = Callable[[Executor, Probe], Unpushed]
Send = Callable[[Executor, Push], tuple[str, ...]]
"""Pushes, and returns the links the remote printed."""


def decide(unpushed: Sequence[Unpushed], *, force: bool = False) -> PushPlan:
    return PushPlan(steps=tuple(_step(u, force) for u in unpushed))


def _step(u: Unpushed, force: bool) -> Push | Skip:
    if u.branch is None:
        return Skip(u.project, u.worktree, "detached")
    if u.ahead == 0:
        return Skip(
            u.project,
            u.worktree,
            "nothing to push" if u.origin_head is None else "up to date",
        )
    if u.branch == u.default_branch:
        raise PreconditionError(
            f"{u.project} is on its default branch {u.branch}; a fork's copy "
            f"of it is not what a PR is opened from.",
            subject=u.project,
        )
    if u.origin_url is None:
        raise PreconditionError(
            f"{u.project} has no origin to push to.",
            subject=u.project,
            remedy="cjdev config origin <fork owner>",
        )
    if u.origin_url == u.upstream_url:
        raise PreconditionError(
            f"{u.project}'s origin is {u.origin_url}, which is upstream; "
            f"upstream is read-only to cjdev.",
            subject=u.project,
        )
    if u.behind and not force:
        raise PreconditionError(
            f"{u.project}: origin's {u.branch} has {u.behind} commit(s) this "
            f"branch does not, so a push would rewrite it.",
            subject=u.project,
            remedy="cjdev push --force-with-lease",
        )
    return Push(
        project=u.project,
        worktree=u.worktree,
        branch=u.branch,
        origin_url=u.origin_url,
        set_upstream=not u.tracked,
        lease=(u.origin_head or "") if force else None,
    )


@final
class PushBranchSet:
    def __init__(
        self,
        manifest: ManifestProvider,
        executor: Executor,
        inspect: Inspect,
        send: Send,
    ) -> None:
        self._manifest = manifest
        self._executor = executor
        self._inspect = inspect
        self._send = send

    def plan(
        self,
        root: Path,
        branch_set: str,
        *,
        force: bool = False,
        observer: RunObserver | None = None,
    ) -> PushPlan:
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
            raise AbortedError("push")
        for result in report.results:
            if result.error is not None:
                raise result.error
        return decide(
            [r.value for r in report.results if r.value is not None], force=force
        )

    def apply(
        self,
        plan: PushPlan,
        *,
        dry_run: bool = False,
        observer: RunObserver | None = None,
    ) -> PushReport:
        report = Runner(1 if dry_run else DEFAULT_NETWORK_JOBS).run(
            [
                Work(key=p.project, label=p.project, action=self._sender(p))
                for p in plan.to_push
            ],
            observer=observer,
        )
        results = {result.label: result for result in report.results}
        rows = []
        for step in plan.steps:
            if isinstance(step, Skip):
                rows.append(Pushed(step.project, step.worktree, None, step.reason))
                continue
            result = results.get(step.project)
            if result is None:
                rows.append(Pushed(step.project, step.worktree, Outcome.CANCELLED))
                continue
            rows.append(
                Pushed(
                    step.project,
                    step.worktree,
                    result.outcome,
                    note=_link(step, result.value) if result.value is not None else "",
                    error=result.error,
                )
            )
        return PushReport(rows=tuple(rows), interrupted=report.interrupted)

    def _prober(self, probe: Probe) -> Callable[[], Unpushed]:
        return lambda: self._inspect(self._executor, probe)

    def _sender(self, push: Push) -> Callable[[], tuple[str, ...]]:
        return lambda: self._send(self._executor, push)


def _link(push: Push, said: tuple[str, ...]) -> str:
    """The link the forge printed, else the fork's own page, where the PR
    button is: a URL built for one forge's PR form would be a guess at its
    routes, and a wrong link is worse than a plain one."""
    if said:
        return said[0]
    return web_page(push.origin_url) or push.origin_url
