"""Reading a workspace and saying what it holds (CFG-4).

The one command that changes nothing, which is what shapes it: there is no
`--dry-run` to honour, no confirmation to collect and no `FileSystem` in
sight. What is left is gather and decide - `_observe` reads the disk, git
answers per project, and `branch_sets_of` turns the answers into the report
without touching anything again.

Its budget is under a second (NFR-5), because it is meant to be run
constantly and possibly from a shell prompt. Six sequential `git` invocations
do not fit that, which is why the per-project queries go through the runner
(PAR-9) even though each one is only reading.
"""

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import final

from cjdev.application.ports import Executor
from cjdev.application.runner import Outcome, Runner, Work
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Manifest
from cjdev.domain.state import (
    Checkout,
    Store,
    WorkspaceStatus,
    active_branch_set,
    branch_sets_of,
)
from cjdev.errors import AbortedError

ReadCheckouts = Callable[[Executor, Path, str], tuple[Checkout, ...]]

DEFAULT_QUERY_JOBS = 8
"""Read-only local git queries: nothing to rate-limit and nothing to
saturate, so this is bounded only because PAR-3 forbids unbounded, and sits
above the project count so the fan-out is one wave."""


@final
class ReportStatus:
    def __init__(
        self,
        manifest: Manifest,
        executor: Executor,
        read_checkouts: ReadCheckouts,
    ) -> None:
        self._manifest = manifest
        self._executor = executor
        self._read_checkouts = read_checkouts

    def perform(
        self, root: Path, *, cwd: Path, jobs: int = DEFAULT_QUERY_JOBS
    ) -> WorkspaceStatus:
        layout = WorkspaceLayout(root)
        provisioned = _observe(layout, self._manifest)

        # fail_fast=False: one unreadable store must not hide the five that
        # read fine. A report is the one thing worth finishing partially, and
        # PAR-5 asks only that the partial state be reported rather than
        # silent - which `Store.error` is.
        report = Runner(jobs, fail_fast=False).run(
            [
                Work(
                    key=project,
                    label=project,
                    action=self._reader(layout, project),
                )
                for project in provisioned
            ]
        )

        # A half-read workspace printed as if it were the whole one is the
        # silent partial result R9 forbids, and here it is indistinguishable
        # from a workspace that really has no branch sets. Nothing was
        # changed, so there is nothing to resume - only nothing to report.
        if report.interrupted:
            raise AbortedError("status")

        failures = {
            result.label: str(result.error)
            for result in report.of(Outcome.FAILED)
            if result.error is not None
        }
        branch_sets = branch_sets_of(
            root,
            [
                checkout
                for result in report.results
                for checkout in (result.value or ())
            ],
        )
        return WorkspaceStatus(
            root=root,
            active=active_branch_set(root, cwd, branch_sets),
            stores=tuple(
                Store(
                    project=project,
                    provisioned=project in provisioned,
                    error=failures.get(project),
                )
                for project in _in_manifest_order(
                    self._manifest,
                    {p.name for p in self._manifest.projects} | set(provisioned),
                )
            ),
            branch_sets=branch_sets,
        )

    def _reader(
        self, layout: WorkspaceLayout, project: str
    ) -> Callable[[], tuple[Checkout, ...]]:
        store = Path(layout.object_store(project))

        def read() -> tuple[Checkout, ...]:
            return self._read_checkouts(self._executor, store, project)

        return read


def _observe(layout: WorkspaceLayout, manifest: Manifest) -> tuple[str, ...]:
    """The projects this workspace actually holds, in manifest order.

    Read off the disk rather than off the manifest, because a workspace's
    project set is what its object stores say it is (CFG-10). A store the
    manifest has since stopped listing is still reported: hiding a directory
    full of fetched objects because a config no longer mentions it is how a
    status report becomes a thing you cannot trust.
    """
    bare = Path(layout.bare_dir)
    if not bare.is_dir():
        return ()
    return _in_manifest_order(
        manifest,
        (store.name.removesuffix(".git") for store in bare.iterdir() if store.is_dir()),
    )


def _in_manifest_order(manifest: Manifest, names: Iterable[str]) -> tuple[str, ...]:
    """Manifest order first, then whatever the manifest has never heard of.

    Manifest order is the tie-break for every ordering cjdev produces, so that
    output cannot depend on scheduling (PAR-4). A store the manifest has no
    opinion about still has to be ordered by something, and its name is the
    only stable thing left.
    """
    known = tuple(project.name for project in manifest.projects)
    remaining = set(names)
    return tuple(
        [name for name in known if name in remaining]
        + sorted(remaining.difference(known))
    )
