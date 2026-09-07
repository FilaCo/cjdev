"""`cjdev clean`: the inverse of `init`, and the most destructive thing here."""

from pathlib import Path

import pytest

from cjdev.application.clean_workspace import CleanWorkspace
from cjdev.application.ports import Executor
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Manifest, Project, ProjectRole
from cjdev.errors import AbortedError, InputRequiredError, PreconditionError
from cjdev.infra.executor.host import HostExecutor
from cjdev.infra.filesystem import HostFileSystem, build_file_system
from cjdev.infra.prompt import NonInteractivePrompt


@pytest.fixture
def manifest() -> Manifest:
    return Manifest(
        schema_version=1,
        projects=(Project("alpha", ProjectRole.BUILDABLE, "file:///nowhere", "main"),),
        build_units=(),
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    layout = WorkspaceLayout(root)
    Path(layout.object_store("alpha")).mkdir(parents=True)
    Path(layout.config_file).write_text("")
    (root / "fix-ice").mkdir()
    return root


def clean(*, yes: bool = True, worktrees=()) -> CleanWorkspace:
    def list_worktrees(executor: Executor, store: Path) -> tuple[str, ...]:
        return tuple(worktrees)

    return CleanWorkspace(
        executor=HostExecutor(),
        file_system=HostFileSystem(),
        prompt=NonInteractivePrompt(assume_yes=yes),
        list_worktrees=list_worktrees,
    )


def test_everything_inside_goes_not_just_the_marker(
    manifest: Manifest, workspace: Path
):
    # Leaving `fix-ice/` behind would leave a directory that looks like a
    # checkout but whose git metadata points into a deleted object store.
    clean().perform(workspace)

    assert list(workspace.iterdir()) == []


def test_the_root_directory_itself_is_left_standing(
    manifest: Manifest, workspace: Path
):
    # Deleting the directory the user is probably standing in leaves their
    # shell somewhere that no longer exists; `rmdir` is theirs to run.
    clean().perform(workspace)

    assert workspace.is_dir()


def test_stray_files_go_too(manifest: Manifest, workspace: Path):
    (workspace / "notes.txt").write_text("scratch")

    clean().perform(workspace)

    assert list(workspace.iterdir()) == []


def test_it_reports_which_projects_it_took_with_it(manifest: Manifest, workspace: Path):
    plan = clean().perform(workspace)

    assert plan.projects == ("alpha",)


def test_declining_leaves_everything_alone(manifest: Manifest, workspace: Path):
    # A person answering "no" is a different case from nobody being there to
    # answer, and only this one can be reached with a real terminal.
    class Declines:
        def confirm(self, question: str, *, destructive: bool = True) -> bool:
            return False

        def choose(self, question, options, *, preselected):
            return tuple(preselected)

    use_case = CleanWorkspace(
        executor=HostExecutor(),
        file_system=HostFileSystem(),
        prompt=Declines(),
        list_worktrees=lambda executor, store: (),
    )

    with pytest.raises(AbortedError):
        use_case.perform(workspace)

    assert workspace.is_dir()


def test_it_refuses_without_a_terminal_and_without_yes(
    manifest: Manifest, workspace: Path
):
    # Deleting a whole workspace is exactly the case where silence must
    # not be read as consent.
    with pytest.raises(InputRequiredError) as refusal:
        clean(yes=False).perform(workspace)

    assert refusal.value.remedy == "re-run with --yes"


class TestStrayWorktrees:
    def test_a_worktree_outside_the_root_blocks_the_removal(
        self, manifest: Manifest, workspace: Path, tmp_path: Path
    ):
        outside = str(tmp_path / "elsewhere")

        with pytest.raises(PreconditionError, match="outside this workspace"):
            clean(worktrees=(outside,)).perform(workspace)

        assert workspace.is_dir()

    def test_force_removes_it_anyway(
        self, manifest: Manifest, workspace: Path, tmp_path: Path
    ):
        outside = str(tmp_path / "elsewhere")

        clean(worktrees=(outside,)).perform(workspace, force=True)

        assert list(workspace.iterdir()) == []

    def test_a_worktree_inside_the_root_is_not_stray(
        self, manifest: Manifest, workspace: Path
    ):
        inside = str(workspace / "fix-ice" / "alpha")

        plan = clean(worktrees=(inside,)).perform(workspace)

        assert plan.stray_worktrees == ()
        assert list(workspace.iterdir()) == []


def test_a_dry_run_removes_nothing(manifest: Manifest, workspace: Path):
    printed: list[str] = []
    use_case = CleanWorkspace(
        executor=HostExecutor(),
        file_system=build_file_system(dry_run=True, emit=printed.append),
        prompt=NonInteractivePrompt(assume_yes=True),
        list_worktrees=lambda executor, store: (),
    )

    use_case.perform(workspace)

    assert sorted(p.name for p in workspace.iterdir()) == [".cjdev", "fix-ice"]
    assert printed == [
        f"rm -rf {workspace / '.cjdev'}",
        f"rm -rf {workspace / 'fix-ice'}",
    ]
