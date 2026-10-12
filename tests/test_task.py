"""A task is a branch set plus its issue: `start`, `issue attach`, `sync`.

The upstreams are real repositories in `tmp_path` over `file://`; only the
forge is a fake, so nothing here reaches the network.
"""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cjdev.bootstrap import Container
from cjdev.cli import cli
from cjdev.domain.build import Profile
from cjdev.domain.forge import (
    DEFAULT_ISSUE_HOME,
    FiledIssue,
    Issue,
    IssueRef,
    NewIssue,
    Repository,
    home_of,
    parse_issue_url,
)
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Project, ProjectRole
from cjdev.domain.record import BranchSetRecord, Task, task_name
from cjdev.errors import ManifestError, PreconditionError, UsageError
from cjdev.infra.config import parse_issue_home
from cjdev.infra.executor.host import HostExecutor
from cjdev.infra.git import provision_object_store
from cjdev.infra.record import read_record, render_record
from conftest import make_upstream

runner = CliRunner()

PROJECTS = ("cangjie_compiler", "cangjie_test")
URL = "https://gitcode.com/Cangjie/cangjie_compiler/issues/812"
BRANCH = "issue-812-bug-ice-on-objcimpl"


class FakeForge:
    def __init__(self, title: str = "[Bug]: ICE on @ObjCImpl") -> None:
        self.read: list[IssueRef] = []
        self._title = title

    def create_issue(self, issue: NewIssue) -> FiledIssue | None:
        raise AssertionError("starting a task files nothing")

    def read_issue(self, ref: IssueRef) -> Issue:
        self.read.append(ref)
        return Issue(ref, self._title)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(repository: Path, name: str) -> str:
    (repository / name).write_text(name)
    git(repository, "add", name)
    git(repository, "commit", "--quiet", "-m", name)
    return git(repository, "rev-parse", "HEAD")


def invoke(where: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.chdir(where)
    return runner.invoke(cli, list(args))


class TestTheName:
    def test_it_is_the_number_and_the_title_as_a_slug(self):
        # Act / Assert
        assert task_name("812", "[Bug]: ICE on @ObjCImpl") == BRANCH

    def test_a_title_with_nothing_ascii_leaves_the_number(self):
        # Act / Assert
        assert task_name("9", "编译器崩溃") == "issue-9"

    def test_a_long_title_is_cut_at_a_word(self):
        # Act
        name = task_name("1", "word " * 20)

        # Assert
        assert name.startswith("issue-1-word-word")
        assert not name.endswith("-")
        assert len(name) <= len("issue-1-") + 40


class TestTheIssueUrl:
    def test_it_names_the_repository_and_the_number(self):
        # Act
        ref = parse_issue_url(URL)

        # Assert
        assert ref == IssueRef(
            Repository("gitcode.com", "Cangjie", "cangjie_compiler"), "812"
        )
        assert ref.url == URL

    @pytest.mark.parametrize(
        "url",
        [
            "https://gitcode.com/Cangjie/cangjie_compiler",
            "https://gitcode.com/Cangjie/cangjie_compiler/pulls/812",
            "http://gitcode.com/Cangjie/cangjie_compiler/issues/812",
            "https://gitcode.com/Cangjie/cangjie_compiler/issues/x",
        ],
    )
    def test_anything_else_is_refused(self, url: str):
        # Act / Assert
        with pytest.raises(UsageError):
            parse_issue_url(url)

    def test_its_home_is_the_project_it_is_filed_against(self):
        # Arrange
        projects = [
            Project(
                name,
                ProjectRole.BUILDABLE,
                f"https://gitcode.com/Cangjie/{name}.git",
                "main",
            )
            for name in PROJECTS
        ]

        # Act / Assert
        assert home_of(parse_issue_url(URL), projects) == "cangjie_compiler"
        with pytest.raises(UsageError, match="no project's upstream"):
            home_of(parse_issue_url(URL.replace("Cangjie", "me")), projects)


class TestTheRecord:
    def test_the_task_and_the_profile_share_one_file(self, tmp_path: Path):
        # Arrange
        path = tmp_path / "set.toml"
        path.write_text(render_record(BranchSetRecord(Profile.DEBUG), path))

        # Act
        path.write_text(render_record(BranchSetRecord(task=Task("p", URL)), path))

        # Assert
        assert read_record(path) == BranchSetRecord(Profile.DEBUG, Task("p", URL))

    def test_what_a_later_command_keeps_under_task_survives(self, tmp_path: Path):
        # Arrange: the PRs of `cjdev pr` go beside the issue.
        path = tmp_path / "set.toml"
        path.write_text('[task]\nhome = "p"\n\n[task.prs]\np = "7"\n')

        # Act
        path.write_text(render_record(BranchSetRecord(task=Task("p", URL)), path))

        # Assert
        text = path.read_text()
        assert 'p = "7"' in text
        assert read_record(path).task == Task("p", URL)

    def test_a_task_that_is_not_a_table_names_the_file(self, tmp_path: Path):
        # Arrange
        path = tmp_path / "set.toml"
        path.write_text('task = "x"\n')

        # Act / Assert
        with pytest.raises(PreconditionError):
            read_record(path)


class TestTheSetting:
    def test_it_defaults_to_the_compiler(self):
        # Act / Assert
        assert parse_issue_home("", source="c") == DEFAULT_ISSUE_HOME

    def test_the_workspace_names_another(self):
        # Act / Assert
        text = '[forge]\nissue_home = "cangjie_runtime"\n'
        assert parse_issue_home(text, source="c") == "cangjie_runtime"

    def test_a_stray_key_is_still_refused(self):
        # Act / Assert
        with pytest.raises(ManifestError):
            parse_issue_home("[forge]\nissue_house = 1\n", source="c")


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    return tmp_path / "remote"


@pytest.fixture
def root(tmp_path: Path, remote: Path, git_available: None) -> Path:
    """Two projects of the bundled manifest, provisioned from upstreams that
    keep moving after `init`."""
    root = tmp_path / "ws"
    layout = WorkspaceLayout(root)
    Path(layout.bare_dir).mkdir(parents=True)
    for name in PROJECTS:
        upstream = make_upstream(remote / name)
        provision_object_store(
            HostExecutor(),
            Path(layout.object_store(name)),
            Project(name, ProjectRole.BUILDABLE, upstream, "main"),
        )
    return root


@pytest.fixture
def forge(monkeypatch: pytest.MonkeyPatch) -> FakeForge:
    fake = FakeForge()
    monkeypatch.setattr(Container, "forge", lambda self, dry_run=False: fake)
    return fake


def record(root: Path, branch_set: str) -> BranchSetRecord:
    return read_record(WorkspaceLayout(root).record(branch_set))


def checkout(root: Path, branch_set: str, project: str) -> Path:
    return Path(WorkspaceLayout(root).worktree(branch_set, project))


class TestStart:
    def test_the_branch_set_is_cut_from_upstream_as_it_is_now(
        self,
        root: Path,
        remote: Path,
        forge: FakeForge,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # Arrange: upstream moved after the workspace was fetched.
        fresh = commit(remote / "cangjie_test", "later")

        # Act
        result = invoke(root, monkeypatch, "start", URL)

        # Assert
        assert result.exit_code == 0, result.output
        assert git(checkout(root, BRANCH, "cangjie_test"), "rev-parse", "HEAD") == fresh
        assert f"cd {root / BRANCH}" in result.output
        assert forge.read == [parse_issue_url(URL)]

    def test_the_task_is_recorded_with_its_issue_and_home(
        self, root: Path, forge: FakeForge, monkeypatch: pytest.MonkeyPatch
    ):
        # Act
        result = invoke(root, monkeypatch, "start", URL, "--name", "fix")

        # Assert
        assert result.exit_code == 0, result.output
        assert record(root, "fix").task == Task("cangjie_compiler", URL)

    def test_without_an_issue_the_home_is_the_workspace_setting(
        self, root: Path, forge: FakeForge, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        config = Path(WorkspaceLayout(root).config_file)
        config.write_text('[forge]\nissue_home = "cangjie_test"\n')

        # Act
        result = invoke(root, monkeypatch, "start", "--no-issue", "fix")

        # Assert
        assert result.exit_code == 0, result.output
        assert record(root, "fix").task == Task("cangjie_test")
        assert forge.read == []

    def test_a_home_no_project_has_is_refused_before_anything_runs(
        self, root: Path, forge: FakeForge, monkeypatch: pytest.MonkeyPatch
    ):
        # Act
        result = invoke(
            root, monkeypatch, "start", "--no-issue", "fix", "--home", "nope"
        )

        # Assert
        assert isinstance(result.exception, ManifestError)
        assert not (root / "fix").exists()

    def test_an_issue_s_home_is_not_overridden(
        self, root: Path, forge: FakeForge, monkeypatch: pytest.MonkeyPatch
    ):
        # Act
        result = invoke(root, monkeypatch, "start", URL, "--home", "cangjie_test")

        # Assert
        assert isinstance(result.exception, UsageError)

    def test_a_dry_run_records_nothing(
        self, root: Path, forge: FakeForge, monkeypatch: pytest.MonkeyPatch
    ):
        # Act
        result = invoke(root, monkeypatch, "start", URL, "--dry-run")

        # Assert
        assert result.exit_code == 0, result.output
        assert "git fetch" in result.output
        assert not Path(WorkspaceLayout(root).record(BRANCH)).exists()

    def test_branch_new_records_no_task(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Act
        result = invoke(root, monkeypatch, "branch", "new", "fix")

        # Assert
        assert result.exit_code == 0, result.output
        assert record(root, "fix").task is None


class TestAttach:
    def test_a_branch_set_gets_its_issue_later(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        invoke(root, monkeypatch, "branch", "new", "fix")

        # Act
        result = invoke(root / "fix", monkeypatch, "issue", "attach", URL)

        # Assert
        assert result.exit_code == 0, result.output
        assert record(root, "fix").task == Task("cangjie_compiler", URL)

    def test_replacing_an_issue_names_the_old_one(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        invoke(root, monkeypatch, "branch", "new", "fix")
        invoke(root / "fix", monkeypatch, "issue", "attach", URL)
        other = "https://gitcode.com/Cangjie/cangjie_test/issues/3"

        # Act
        result = invoke(root / "fix", monkeypatch, "issue", "attach", other)

        # Assert
        assert result.exit_code == 0, result.output
        assert f"replaces {URL}" in result.output
        assert record(root, "fix").task == Task("cangjie_test", other)


@pytest.fixture
def started(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The branch set `fix`, with an identity to commit as."""
    invoke(root, monkeypatch, "branch", "new", "fix")
    for name in PROJECTS:
        worktree = checkout(root, "fix", name)
        git(worktree, "config", "user.email", "test@example.invalid")
        git(worktree, "config", "user.name", "Test")
    return root / "fix"


class TestSync:
    def test_a_branch_with_no_commits_of_its_own_is_fast_forwarded(
        self, root: Path, remote: Path, started: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        fresh = commit(remote / "cangjie_compiler", "later")

        # Act
        result = invoke(started, monkeypatch, "sync")

        # Assert
        assert result.exit_code == 0, result.output
        worktree = checkout(root, "fix", "cangjie_compiler")
        assert git(worktree, "rev-parse", "HEAD") == fresh
        assert "fast-forwarded 1 commit(s)" in result.output
        assert "up to date" in result.output

    def test_a_diverged_branch_is_reported_and_left_alone(
        self, root: Path, remote: Path, started: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        commit(remote / "cangjie_test", "theirs")
        mine = commit(checkout(root, "fix", "cangjie_test"), "mine")

        # Act
        result = invoke(started, monkeypatch, "sync")

        # Assert: a rebase rewrites what may already be pushed.
        assert result.exit_code == 0, result.output
        assert git(checkout(root, "fix", "cangjie_test"), "rev-parse", "HEAD") == mine
        said = " ".join(result.output.split())
        assert "diverged: 1 ahead, 1 behind upstream/main" in said
        assert "`git rebase upstream/main` in it" in said

    def test_a_dry_run_moves_nothing(
        self, root: Path, remote: Path, started: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        commit(remote / "cangjie_compiler", "later")
        worktree = checkout(root, "fix", "cangjie_compiler")
        before = git(worktree, "rev-parse", "HEAD")

        # Act
        result = invoke(started, monkeypatch, "sync", "--dry-run")

        # Assert
        assert result.exit_code == 0, result.output
        assert git(worktree, "rev-parse", "HEAD") == before
        assert "git fetch" in result.output
