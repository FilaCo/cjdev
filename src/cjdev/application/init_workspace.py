"""Creating a workspace, and changing which projects it holds.

The three phases are kept apart on purpose. `observe` touches the filesystem,
`decide` is pure and is what the tests assert on, and `perform` is the only
part that changes anything. Preflight is that split made visible: by the time
the first directory is created, every decision has been taken.

Run again on an existing workspace, this is how the project set is changed:
the selection starts from what is on disk, and unchecking something removes
it. That makes `init` the one place that answers "which projects is this
workspace about", instead of a create-only command plus a separate one for
every later adjustment.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path, PurePath
from typing import final

from cjdev.application.ports import Executor, FileSystem, Prompt
from cjdev.application.runner import Runner, RunObserver, RunReport, Work
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Manifest, Project
from cjdev.errors import AbortedError

Provision = Callable[[Executor, Path, Project], None]
Remove = Callable[[Executor, FileSystem, Path, Project], None]


@final
@dataclass(frozen=True)
class Observed:
    provisioned: frozenset[str]
    """Projects whose object store already exists. The workspace's own answer
    to "which projects am I about" - not a list kept in a file that could
    disagree with the disk."""
    config_exists: bool


@final
@dataclass(frozen=True)
class InitPlan:
    directories: tuple[PurePath, ...]
    config_file: PurePath
    write_config: bool
    projects: tuple[Project, ...]
    provisioned: frozenset[str]
    selected: frozenset[str]

    @property
    def to_provision(self) -> tuple[Project, ...]:
        return tuple(
            p
            for p in self.projects
            if p.name in self.selected and p.name not in self.provisioned
        )

    @property
    def to_remove(self) -> tuple[Project, ...]:
        return tuple(
            p
            for p in self.projects
            if p.name in self.provisioned and p.name not in self.selected
        )

    @property
    def is_noop(self) -> bool:
        return not self.to_provision and not self.to_remove and not self.write_config

    def with_selection(self, names: frozenset[str]) -> "InitPlan":
        return replace(self, selected=names)


def observe(layout: WorkspaceLayout, manifest: Manifest) -> Observed:
    return Observed(
        provisioned=frozenset(
            project.name
            for project in manifest.projects
            if Path(layout.object_store(project.name)).is_dir()
        ),
        config_exists=Path(layout.config_file).is_file(),
    )


def decide(layout: WorkspaceLayout, manifest: Manifest, observed: Observed) -> InitPlan:
    # An existing workspace starts from what it already holds, so the wizard
    # shows the truth and an unchanged answer is a no-op. Only a fresh one
    # falls back to the manifest's default group.
    default = (
        observed.provisioned
        if observed.provisioned
        else frozenset(p.name for p in manifest.default_projects())
    )
    return InitPlan(
        # No `cache/` yet: nothing reads it until builds land, and an empty
        # directory is a promise the tool is not keeping.
        directories=(layout.marker, layout.bare_dir),
        config_file=layout.config_file,
        write_config=not observed.config_exists,
        projects=manifest.projects,
        provisioned=observed.provisioned,
        selected=default,
    )


@final
class InitWorkspace:
    def __init__(
        self,
        manifest: Manifest,
        executor: Executor,
        file_system: FileSystem,
        prompt: Prompt,
        provision: Provision,
        remove: Remove,
        render_config: Callable[[], str],
    ) -> None:
        self._manifest = manifest
        self._executor = executor
        self._fs = file_system
        self._prompt = prompt
        self._provision = provision
        self._remove = remove
        self._render_config = render_config

    def plan(self, root: Path) -> InitPlan:
        """Everything `perform` would do, decided without doing any of it."""
        layout = WorkspaceLayout(root)
        return decide(layout, self._manifest, observe(layout, self._manifest))

    def perform(
        self,
        root: Path,
        *,
        jobs: int,
        dry_run: bool = False,
        observer: RunObserver | None = None,
    ) -> RunReport[None]:
        """plan, agree and apply in one call, for callers with nothing to do
        in between. The CLI keeps them apart because it cannot know what to
        display until the answers are in."""
        plan = self.agree(self.plan(root), root)
        return self.apply(root, plan, jobs=jobs, dry_run=dry_run, observer=observer)

    def apply(
        self,
        root: Path,
        plan: InitPlan,
        *,
        jobs: int,
        dry_run: bool = False,
        observer: RunObserver | None = None,
    ) -> RunReport[None]:
        layout = WorkspaceLayout(root)
        # Built before the first directory rather than where it is used: the
        # job count is validated here, and a usage error that has already
        # created half a workspace is worse than the one it reports.
        #
        # A dry run prints in sequential order: there is no work to overlap,
        # and its whole output would otherwise be at the mercy of the
        # scheduler.
        runner = Runner(1 if dry_run else jobs)
        if plan.is_noop:
            return RunReport(())

        for directory in plan.directories:
            self._fs.mkdir(directory)
        if plan.write_config:
            self._fs.write_text(layout.config_file, self._render_config())

        return runner.run(self._work(layout, plan), observer=observer)

    def _work(self, layout: WorkspaceLayout, plan: InitPlan) -> list[Work[None]]:
        return [
            # Keyed by project: the whole point of one object store per
            # project is that they are independent.
            Work(key=p.name, label=p.name, action=self._provisioner(layout, p))
            for p in plan.to_provision
        ] + [
            Work(key=p.name, label=p.name, action=self._remover(layout, p))
            for p in plan.to_remove
        ]

    def agree(self, plan: InitPlan, root: Path) -> InitPlan:
        """Settle every question before the first side effect.

        The settings and the consent are collected separately, because ticking
        a project set says nothing about agreeing to delete what is no longer
        in it.
        """
        names = tuple(project.name for project in plan.projects)
        plan = plan.with_selection(
            frozenset(
                self._prompt.choose(
                    "Projects in this workspace",
                    names,
                    preselected=sorted(plan.selected),
                )
            )
        )
        question, destructive = self._question(plan, root)
        if not self._prompt.confirm(question, destructive=destructive):
            raise AbortedError("init")
        return plan

    @staticmethod
    def _question(plan: InitPlan, root: Path) -> tuple[str, bool]:
        """Deleting a store throws away everything fetched into it, so a plan
        that removes anything asks as a destructive one - which is also what
        makes it refuse rather than proceed with no terminal."""
        fetching = f"fetch {len(plan.to_provision)} project(s)"
        if not plan.to_remove:
            return f"Set up {root} and {fetching}?", False
        removing = ", ".join(p.name for p in plan.to_remove)
        return (
            f"In {root}: {fetching}, and DELETE the fetched objects of {removing}?",
            True,
        )

    def _provisioner(
        self, layout: WorkspaceLayout, project: Project
    ) -> Callable[[], None]:
        store = Path(layout.object_store(project.name))

        def provision() -> None:
            self._provision(self._executor, store, project)

        return provision

    def _remover(self, layout: WorkspaceLayout, project: Project) -> Callable[[], None]:
        store = Path(layout.object_store(project.name))

        def remove() -> None:
            self._remove(self._executor, self._fs, store, project)

        return remove
