"""`cjdev config origin`, `commit` and `push`, end to end against a real git.

The forks are bare repositories next to the upstreams in `tmp_path`, reached
over `file://`: what `push --set-upstream` records and which remote-tracking
ref a push updates are facts about git, and only git can state them.
"""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cjdev.cli import cli
from cjdev.domain.environment import DEFAULT_ENVIRONMENT
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Project, ProjectRole
from cjdev.errors import PreconditionError
from cjdev.infra.config import (
    load_fork_owner,
    record_fork_owner,
    render_workspace_config,
)
from cjdev.infra.executor.host import HostExecutor
from cjdev.infra.filesystem import HostFileSystem
from cjdev.infra.git import provision_object_store, read_store
from conftest import make_upstream

pytestmark = pytest.mark.usefixtures("git_available")

runner = CliRunner()

PROJECTS = ("cangjie_compiler", "cangjie_test")
BRANCH = "fix/ice"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    return tmp_path / "remote"


@pytest.fixture
def root(tmp_path: Path, remote: Path) -> Path:
    """Two projects of the bundled manifest, a fork of each under `me`, and
    the branch set `fix/ice` cut from upstream."""
    root = tmp_path / "ws"
    layout = WorkspaceLayout(root)
    Path(layout.bare_dir).mkdir(parents=True)
    for name in PROJECTS:
        upstream = make_upstream(remote / "Cangjie" / name)
        (remote / "me" / name).mkdir(parents=True)
        git(remote / "me" / name, "init", "--bare", "--quiet")
        store = Path(layout.object_store(name))
        provision_object_store(
            HostExecutor(),
            store,
            Project(name, ProjectRole.BUILDABLE, upstream, "main"),
        )
        git(store, "config", "user.email", "test@example.invalid")
        git(store, "config", "user.name", "Test")
        git(
            store,
            "worktree",
            "add",
            "--quiet",
            "--no-track",
            "-b",
            BRANCH,
            str(layout.worktree(BRANCH, name)),
            "refs/remotes/upstream/main",
        )
    return root


def checkout(root: Path, project: str) -> Path:
    return Path(WorkspaceLayout(root).worktree(BRANCH, project))


def store(root: Path, project: str) -> Path:
    return Path(WorkspaceLayout(root).object_store(project))


def change(root: Path, project: str, text: str = "fixed") -> None:
    worktree = checkout(root, project)
    (worktree / "README").write_text(text)
    git(worktree, "add", "README")


def invoke(where: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.chdir(where)
    return runner.invoke(cli, list(args))


class TestOrigin:
    def test_every_project_gets_its_fork_and_the_owner_is_recorded(
        self, root: Path, remote: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Act
        result = invoke(root, monkeypatch, "config", "origin", "me")

        # Assert
        assert result.exit_code == 0, result.output
        for name in PROJECTS:
            url = git(store(root, name), "remote", "get-url", "origin")
            assert url == f"file://{remote}/me/{name}"
        assert load_fork_owner(root) == "me"

    def test_an_origin_pointing_elsewhere_is_reported_and_kept(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        theirs = "file:///elsewhere/cangjie_test"
        git(store(root, "cangjie_test"), "remote", "add", "origin", theirs)

        # Act
        result = invoke(root, monkeypatch, "config", "origin", "me")

        # Assert
        assert result.exit_code == 0, result.output
        assert git(store(root, "cangjie_test"), "remote", "get-url", "origin") == theirs
        assert "kept" in result.output

    def test_init_wires_origin_too(
        self, root: Path, remote: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Act
        result = invoke(
            root, monkeypatch, "init", str(root), "--fork-owner", "me", "--dry-run"
        )

        # Assert
        assert result.exit_code == 0, result.output
        assert f"git remote add origin file://{remote}/me/cangjie_test" in (
            result.output
        )
        assert git(store(root, "cangjie_test"), "remote") == "upstream"

    def test_without_an_owner_it_names_the_fix(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Act
        result = invoke(root, monkeypatch, "config", "origin")

        # Assert
        assert isinstance(result.exception, PreconditionError)
        assert result.exception.remedy == "cjdev config origin <fork owner>"


def test_recording_the_owner_keeps_the_rest_of_the_file(tmp_path: Path):
    # Arrange
    config = Path(WorkspaceLayout(tmp_path).config_file)
    config.parent.mkdir()
    config.write_text(render_workspace_config(DEFAULT_ENVIRONMENT))

    # Act
    record_fork_owner(HostFileSystem(), tmp_path, "me")

    # Assert
    assert load_fork_owner(tmp_path) == "me"
    assert config.read_text().startswith("# cjdev workspace configuration.")


class TestCommit:
    def test_one_message_signed_off_in_every_project_with_changes(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        change(root, "cangjie_compiler")
        untouched = git(checkout(root, "cangjie_test"), "rev-parse", "HEAD")

        # Act
        result = invoke(
            checkout(root, "cangjie_compiler"),
            monkeypatch,
            "commit",
            "-m",
            "fix(sema): the ICE",
        )

        # Assert
        assert result.exit_code == 0, result.output
        body = git(checkout(root, "cangjie_compiler"), "log", "-1", "--format=%B")
        assert body.startswith("fix(sema): the ICE")
        assert "Signed-off-by: Test <test@example.invalid>" in body
        assert git(checkout(root, "cangjie_test"), "rev-parse", "HEAD") == untouched
        assert "nothing to commit" in result.output

    def test_all_takes_unstaged_tracked_changes(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        (checkout(root, "cangjie_test") / "README").write_text("unstaged")

        # Act
        result = invoke(
            checkout(root, "cangjie_test"), monkeypatch, "commit", "-a", "-m", "test"
        )

        # Assert
        assert result.exit_code == 0, result.output
        assert git(checkout(root, "cangjie_test"), "status", "--porcelain") == ""


class TestPush:
    @pytest.fixture
    def committed(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        invoke(root, monkeypatch, "config", "origin", "me")
        change(root, "cangjie_compiler")
        invoke(checkout(root, "cangjie_compiler"), monkeypatch, "commit", "-m", "fix")
        return root

    def test_only_what_is_ahead_goes_to_the_fork_with_tracking_set(
        self, committed: Path, remote: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Act
        result = invoke(checkout(committed, "cangjie_compiler"), monkeypatch, "push")

        # Assert
        assert result.exit_code == 0, result.output
        head = git(checkout(committed, "cangjie_compiler"), "rev-parse", "HEAD")
        fork = remote / "me"
        assert git(fork / "cangjie_compiler", "rev-parse", BRANCH) == head
        assert git(fork / "cangjie_test", "branch", "--list") == ""
        tracking = git(
            store(committed, "cangjie_compiler"), "config", "branch.fix/ice.remote"
        )
        assert tracking == "origin"
        assert "nothing to push" in result.output

    def test_status_then_shows_what_is_still_unpushed(
        self, committed: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        invoke(checkout(committed, "cangjie_compiler"), monkeypatch, "push")
        change(committed, "cangjie_compiler", "again")
        invoke(
            checkout(committed, "cangjie_compiler"), monkeypatch, "commit", "-m", "2"
        )

        # Act
        reading = read_store(
            HostExecutor(), store(committed, "cangjie_compiler"), "cangjie_compiler"
        )

        # Assert
        (tracked,) = reading.checkouts
        origin = next(t for t in tracked.tracking if t.remote == "origin")
        assert (origin.ahead, origin.behind) == (1, 0)

    def test_the_link_the_forge_prints_is_the_one_reported(
        self, committed: Path, remote: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        link = "https://forge.invalid/me/cangjie_compiler/pull/new/fix/ice"
        hook = remote / "me" / "cangjie_compiler" / "hooks" / "post-receive"
        hook.write_text(f"#!/bin/sh\necho 'Create a PR:'\necho '  {link}'\n")
        hook.chmod(0o755)

        # Act
        result = invoke(checkout(committed, "cangjie_compiler"), monkeypatch, "push")

        # Assert
        assert result.exit_code == 0, result.output
        assert link in result.output.replace("\n", "").replace(" ", "")

    def test_a_rewrite_needs_the_lease(
        self, committed: Path, remote: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        worktree = checkout(committed, "cangjie_compiler")
        invoke(worktree, monkeypatch, "push")
        git(worktree, "commit", "--amend", "--quiet", "-m", "fix, reworded")

        # Act
        refused = invoke(worktree, monkeypatch, "push")
        forced = invoke(worktree, monkeypatch, "push", "--force-with-lease")

        # Assert
        assert isinstance(refused.exception, PreconditionError)
        assert forced.exit_code == 0, forced.output
        fork = remote / "me" / "cangjie_compiler"
        assert git(fork, "rev-parse", BRANCH) == git(worktree, "rev-parse", "HEAD")

    def test_without_origin_it_names_the_fix(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        change(root, "cangjie_compiler")
        invoke(checkout(root, "cangjie_compiler"), monkeypatch, "commit", "-m", "fix")

        # Act
        result = invoke(checkout(root, "cangjie_compiler"), monkeypatch, "push")

        # Assert
        assert isinstance(result.exception, PreconditionError)
        assert result.exception.remedy == "cjdev config origin <fork owner>"
