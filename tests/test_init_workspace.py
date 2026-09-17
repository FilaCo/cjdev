"""`cjdev init`, end to end against a real git.

The real binary, so these clone from the `file://` repositories `conftest`
builds rather than from a fake - it catches which refs a bare `init` + `fetch`
actually produces, and where `remote set-head` puts `HEAD`.
"""

import shutil
import subprocess
from pathlib import Path, PurePath

import pytest

from cjdev.application.init_workspace import (
    InitWorkspace,
    Observed,
    decide,
)
from cjdev.application.ports import Command
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Manifest, Project, ProjectRole
from cjdev.errors import PreconditionError, UsageError
from cjdev.infra.config import render_workspace_config
from cjdev.infra.executor import build_executor
from cjdev.infra.executor.host import HostExecutor
from cjdev.infra.filesystem import HostFileSystem, build_file_system
from cjdev.infra.git import Git, provision_object_store, remove_object_store
from cjdev.infra.prompt import NonInteractivePrompt
from conftest import make_upstream

pytestmark = pytest.mark.usefixtures("git_available")


def dry_run_workspace(manifest: Manifest, printed: list[str]) -> InitWorkspace:
    return InitWorkspace(
        manifest=lambda: manifest,
        executor=build_executor(dry_run=True, emit=printed.append),
        file_system=build_file_system(dry_run=True, emit=printed.append),
        prompt=NonInteractivePrompt(assume_yes=False),
        provision=provision_object_store,
        remove=remove_object_store,
        render_config=render_workspace_config,
    )


def init_workspace(manifest: Manifest) -> InitWorkspace:
    """Wired by hand rather than through `Container`, which necessarily binds
    the bundled manifest and its gitcode URLs."""
    return InitWorkspace(
        manifest=lambda: manifest,
        executor=HostExecutor(),
        file_system=HostFileSystem(),
        prompt=NonInteractivePrompt(assume_yes=False),
        provision=provision_object_store,
        remove=remove_object_store,
        render_config=render_workspace_config,
    )


@pytest.fixture
def manifest(tmp_path: Path) -> Manifest:
    return Manifest(
        schema_version=1,
        projects=tuple(
            Project(
                name=name,
                role=ProjectRole.BUILDABLE,
                upstream_url=make_upstream(tmp_path / "upstreams" / name),
                default_branch="main",
            )
            for name in ("alpha", "beta")
        ),
        build_units=(),
    )


class TestDecide:
    """The pure half. No filesystem, no git."""

    def test_a_fresh_workspace_provisions_every_project(self, manifest: Manifest):
        layout = WorkspaceLayout(PurePath("/ws"))

        plan = decide(layout, manifest, Observed(frozenset(), config_exists=False))

        assert [p.name for p in plan.to_provision] == ["alpha", "beta"]
        assert plan.write_config
        assert layout.bare_dir in plan.directories
        # No cache/ until something reads it; that lands with the builds.
        assert layout.ccache_dir not in plan.directories

    def test_re_running_tops_up_only_what_is_missing(self, manifest: Manifest):
        # Idempotence is the point: `init` on a half-built workspace should
        # finish the job, not fail and not re-clone what is already there.
        plan = decide(
            WorkspaceLayout(PurePath("/ws")),
            manifest,
            Observed(frozenset({"alpha"}), config_exists=True),
        )

        # The selection starts from what is on disk, so an unchanged answer
        # provisions nothing and removes nothing.
        assert plan.to_provision == ()
        assert plan.to_remove == ()
        assert not plan.write_config

    def test_a_complete_workspace_needs_nothing(self, manifest: Manifest):
        plan = decide(
            WorkspaceLayout(PurePath("/ws")),
            manifest,
            Observed(frozenset({"alpha", "beta"}), config_exists=True),
        )

        assert plan.is_noop

    def test_adding_to_the_selection_provisions_the_difference(
        self, manifest: Manifest
    ):
        plan = decide(
            WorkspaceLayout(PurePath("/ws")),
            manifest,
            Observed(frozenset({"alpha"}), config_exists=True),
        ).with_selection(frozenset({"alpha", "beta"}))

        assert [p.name for p in plan.to_provision] == ["beta"]
        assert plan.to_remove == ()

    def test_dropping_from_the_selection_removes_it(self, manifest: Manifest):
        # Unchecking an existing project is how `init` doubles as the way to
        # change a workspace, rather than only create one.
        plan = decide(
            WorkspaceLayout(PurePath("/ws")),
            manifest,
            Observed(frozenset({"alpha", "beta"}), config_exists=True),
        ).with_selection(frozenset({"alpha"}))

        assert [p.name for p in plan.to_remove] == ["beta"]
        assert plan.to_provision == ()

    def test_a_fresh_workspace_starts_from_the_manifests_default_group(self):
        # The bundled manifest offers the minimal SDK, not all six projects.
        from cjdev.infra.config import load_bundled_manifest

        bundled = load_bundled_manifest()
        plan = decide(
            WorkspaceLayout(PurePath("/ws")),
            bundled,
            Observed(frozenset(), config_exists=False),
        )

        assert [p.name for p in plan.to_provision] == [
            "cangjie_compiler",
            "cangjie_runtime",
            "cangjie_tools",
        ]


class TestJobCount:
    def test_a_bad_job_count_fails_before_anything_is_created(
        self, tmp_path: Path, manifest: Manifest
    ):
        # A usage error that has already written half a workspace is worse
        # than the one it reports, so the count is checked ahead of the first
        # `mkdir` rather than where the runner happens to be built.
        root = tmp_path / "ws"
        root.mkdir()
        use_case = init_workspace(manifest)

        with pytest.raises(UsageError):
            use_case.apply(root, use_case.plan(root), jobs=0)

        assert list(root.iterdir()) == []


class TestEndToEnd:
    @pytest.fixture
    def initialised(self, tmp_path: Path, manifest: Manifest) -> WorkspaceLayout:
        root = tmp_path / "ws"
        root.mkdir()
        report = init_workspace(manifest).perform(root, jobs=2)

        assert report.ok, [str(r.error) for r in report.results]
        return WorkspaceLayout(root)

    def test_the_tree_is_the_documented_one(self, initialised: WorkspaceLayout):
        root = Path(initialised.root)

        assert sorted(p.name for p in root.iterdir()) == [".cjdev"]
        assert Path(initialised.config_file).is_file()
        assert Path(initialised.bare_dir).is_dir()
        # No cache/ until something reads it: an empty directory is a promise
        # the tool is not keeping.
        assert not Path(initialised.cache_dir).exists()

    def test_each_project_gets_a_bare_store(self, initialised: WorkspaceLayout):
        for name in ("alpha", "beta"):
            store = Path(initialised.object_store(name))
            assert (store / "HEAD").is_file()
            assert not (store / ".git").exists()

    def test_upstream_refs_land_under_refs_remotes(self, initialised: WorkspaceLayout):
        # The reason `init` does not use `git clone --bare`: a bare clone
        # writes branches into refs/heads/* and creates no refs/remotes/*,
        # leaving nothing to fast-forward the local default branch from.
        store = Path(initialised.object_store("alpha"))

        assert (store / "refs" / "remotes" / "upstream" / "main").is_file()
        assert not (store / "refs" / "heads" / "main").is_file()

    def test_the_default_branch_is_detected_rather_than_assumed(
        self, initialised: WorkspaceLayout
    ):
        # The sync commands read this ref back instead of hardcoding
        # main/master/dev.
        head = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/upstream/HEAD"],
            cwd=Path(initialised.object_store("alpha")),
            capture_output=True,
            text=True,
            check=True,
        )

        assert head.stdout.strip() == "refs/remotes/upstream/main"

    def test_running_init_again_changes_nothing_and_still_succeeds(
        self, initialised: WorkspaceLayout, manifest: Manifest
    ):
        marker = Path(initialised.config_file)
        marker.write_text("# edited by hand\n")

        report = init_workspace(manifest).perform(Path(initialised.root), jobs=2)

        assert report.ok
        assert marker.read_text() == "# edited by hand\n"


class TestProvisioning:
    def test_a_project_with_an_unreachable_upstream_fails_with_its_output(
        self, tmp_path: Path
    ):
        from cjdev.errors import CommandError

        store = tmp_path / "broken.git"
        store.parent.mkdir(exist_ok=True)
        project = Project(
            name="broken",
            role=ProjectRole.BUILDABLE,
            upstream_url=f"file://{tmp_path / 'does-not-exist'}",
            default_branch="main",
        )

        with pytest.raises(CommandError) as caught:
            provision_object_store(HostExecutor(), store, project)

        assert "does-not-exist" in str(caught.value)


class TestDroppingAProjectWithRegistrationsLeft:
    """`remove_object_store` refuses while the store still has worktree
    registrations, stale ones included - the why is recorded on
    `Git.worktrees`, the guard this behavior reads."""

    @pytest.fixture
    def registered_worktree(
        self, tmp_path: Path, manifest: Manifest
    ) -> tuple[Path, Path, Project]:
        """A store with one live checkout, before anything breaks it."""
        root = tmp_path / "ws"
        layout = WorkspaceLayout(root)
        Path(layout.bare_dir).mkdir(parents=True)
        project = manifest.projects[0]
        store = Path(layout.object_store(project.name))
        provision_object_store(HostExecutor(), store, project)
        worktree = root / "main" / project.name
        subprocess.run(
            (
                "git",
                "-C",
                str(store),
                "worktree",
                "add",
                "--quiet",
                str(worktree),
                "-b",
                "main",
                "upstream/main",
            ),
            check=True,
            capture_output=True,
        )
        return store, worktree, project

    @pytest.fixture
    def moved_away(
        self, registered_worktree: tuple[Path, Path, Project]
    ) -> tuple[Path, Path, Project]:
        store, worktree, project = registered_worktree
        # The checkout is alive at its new path, the registration still
        # names the old one: exactly the state an on-disk test would call
        # "nothing left to break".
        moved = worktree.parent / (worktree.name + "-moved")
        worktree.rename(moved)
        return store, worktree, project

    @pytest.fixture
    def deleted(
        self, registered_worktree: tuple[Path, Path, Project]
    ) -> tuple[Path, Path, Project]:
        store, worktree, project = registered_worktree
        # The checkout was removed by hand, the registration is all that is
        # left: the only case where a prune is the right first move - a
        # moved checkout (above) has to be repaired first.
        shutil.rmtree(worktree)
        return store, worktree, project

    def test_a_stale_registration_still_blocks_the_drop(
        self, moved_away: tuple[Path, Path, Project]
    ):
        store, registered_path, project = moved_away

        with pytest.raises(PreconditionError) as caught:
            remove_object_store(HostExecutor(), HostFileSystem(), store, project)

        assert str(registered_path) in str(caught.value)
        assert "worktree prune" in str(caught.value)
        # The moved hint travels with the prune: without it the refusal
        # names exactly the command that would destroy this checkout's
        # newest commits two steps later.
        assert "worktree repair" in str(caught.value)
        # Nothing dropped while the reader is being asked.
        assert store.exists()

    def test_pruning_the_registrations_clears_the_refusal(
        self, deleted: tuple[Path, Path, Project]
    ):
        # The refusal names the command that unblocks it; running it - the
        # reader's decision, not cjdev's - lets the drop go through. The
        # worktree here was deleted, the case prune exists for; pinning the
        # prune to the moved fixture instead would assert the very loss the
        # moved hint stands against.
        store, _, project = deleted

        subprocess.run(
            ("git", "-C", str(store), "worktree", "prune"),
            check=True,
            capture_output=True,
        )
        remove_object_store(HostExecutor(), HostFileSystem(), store, project)

        assert not store.exists()


class TestGitIsReadOnlyWhereItClaims:
    def test_listing_remotes_survives_a_dry_run(self, tmp_path: Path):
        # `observe` has to work under --dry-run or the plan is a guess.
        recorded: list[Command] = []

        class Recorder:
            def run(self, command: Command, *, check: bool = True):
                recorded.append(command)
                return HostExecutor().run(command, check=check)

        path = tmp_path / "repo"
        make_upstream(path)
        Git(Recorder()).remotes(path)

        assert [c.mutates for c in recorded] == [False]


def test_the_rendered_config_is_valid_toml_and_carries_its_comments():
    import tomlkit

    text = render_workspace_config()

    assert tomlkit.parse(text) is not None
    assert "cjdev config show" in text


class TestDryRun:
    def test_it_changes_nothing_at_all(self, tmp_path: Path, manifest: Manifest):
        # The workspace skeleton is written outside the executor, so it is
        # the part that quietly escapes a dry run.
        root = tmp_path / "ws"
        root.mkdir()
        printed: list[str] = []
        init = dry_run_workspace(manifest, printed)

        init.perform(root, jobs=2, dry_run=True)

        assert list(root.iterdir()) == []

    def test_it_prints_the_commands_it_would_run(
        self, tmp_path: Path, manifest: Manifest
    ):
        root = tmp_path / "ws"
        root.mkdir()
        printed: list[str] = []
        dry_run_workspace(manifest, printed).perform(root, jobs=2, dry_run=True)

        # The workspace skeleton first, then each project whole and in
        # manifest order, never interleaved.
        assert [line.split()[0] for line in printed[:3]] == [
            "mkdir",
            "mkdir",
            "write",
        ]
        git = [line for line in printed if line.startswith("git ")]
        assert [line.split()[1] for line in git] == [
            "init",
            "remote",
            "fetch",
            "remote",
        ] * 2
        assert "alpha" in git[0] and "beta" in git[4]
