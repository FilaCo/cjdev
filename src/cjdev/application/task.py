"""`cjdev start` and `cjdev issue attach`: a task is a branch set plus the
issue it is for, kept in the branch set's record (ADR-0045).

`start` checks the branch set out through `NewBranchSet`; what is added here
is the issue, the fetch that makes the base fresh, and the record.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import final

from cjdev.application.branch_set_profile import ReadRecord, RenderRecord
from cjdev.application.ports import Executor, FileSystem, Forge
from cjdev.application.report_status import ManifestProvider
from cjdev.application.runner import DEFAULT_NETWORK_JOBS, Runner, RunObserver, Work
from cjdev.application.workspace import held_projects
from cjdev.domain.forge import home_of, parse_issue_url
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.record import BranchSetRecord, Task, task_name
from cjdev.errors import AbortedError, UsageError

Fetch = Callable[[Executor, PurePath], None]
"""One object store, from `upstream`."""


@final
@dataclass(frozen=True)
class Start:
    branch_set: str
    task: Task


@final
class Tasks:
    def __init__(
        self,
        manifest: ManifestProvider,
        executor: Executor,
        file_system: FileSystem,
        forge: Forge,
        fetch: Fetch,
        read: ReadRecord,
        render: RenderRecord,
        issue_home: Callable[[], str],
    ) -> None:
        self._manifest = manifest
        self._executor = executor
        self._fs = file_system
        self._forge = forge
        self._fetch = fetch
        self._read = read
        self._render = render
        self._issue_home = issue_home

    def start(
        self,
        subject: str,
        *,
        no_issue: bool = False,
        name: str | None = None,
        home: str | None = None,
    ) -> Start:
        """`subject` is the issue URL, or with `no_issue` the branch set."""
        manifest = self._manifest()
        if no_issue:
            if name is not None:
                raise UsageError(
                    "with --no-issue the argument is the name; drop --name."
                )
            home = manifest.project(home or self._issue_home()).name
            return Start(subject, Task(home=home))
        if home is not None:
            raise UsageError(
                "--home goes with --no-issue: an issue's home is the project "
                "it is filed against."
            )
        ref = parse_issue_url(subject)
        task = Task(home=home_of(ref, manifest.projects), issue=ref.url)
        # Read even when --name spares the title: a mistyped number is cheaper
        # to find out about before six checkouts than after.
        issue = self._forge.read_issue(ref)
        return Start(name or task_name(ref.number, issue.title), task)

    def fetch(
        self,
        root: Path,
        *,
        jobs: int = DEFAULT_NETWORK_JOBS,
        observer: RunObserver | None = None,
    ) -> None:
        """Every held project, so the branch set starts from upstream as it
        is now and not as it was at `init`."""
        layout = WorkspaceLayout(root)
        report = Runner(jobs).run(
            [
                Work(key=p, label=p, action=self._fetcher(layout.object_store(p)))
                for p in held_projects(layout, self._manifest())
            ],
            observer=observer,
        )
        if report.interrupted:
            raise AbortedError("start")
        for result in report.results:
            if result.error is not None:
                raise result.error

    def remember(self, root: Path, branch_set: str, task: Task) -> None:
        path = WorkspaceLayout(root).record(branch_set)
        self._fs.mkdir(path.parent)
        self._fs.write_text(path, self._render(BranchSetRecord(task=task), path))

    def attach(self, root: Path, branch_set: str, url: str) -> tuple[Task, str | None]:
        """The task, and the issue it replaced, if any."""
        ref = parse_issue_url(url)
        task = Task(home=home_of(ref, self._manifest().projects), issue=ref.url)
        before = self._read(WorkspaceLayout(root).record(branch_set)).task
        self.remember(root, branch_set, task)
        return task, before.issue if before is not None else None

    def _fetcher(self, store: PurePath) -> Callable[[], None]:
        return lambda: self._fetch(self._executor, store)
