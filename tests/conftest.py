"""What more than one suite needs from a real git.

The real `git` binary, so the suites that exercise `infra/git.py`
build repositories in a `tmp_path` rather than faking one. It costs
milliseconds and it catches what a fake never would - which refs a bare `init`
plus `fetch` actually produces, and what `worktree list --porcelain` prints
for a detached checkout.
"""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def git_available() -> None:
    if subprocess.run(["git", "--version"], capture_output=True).returncode:
        pytest.skip("git is not installed")


def make_upstream(path: Path, branch: str = "main") -> str:
    """A real repository with one commit, served over `file://`."""
    path.mkdir(parents=True)
    run = lambda *args: subprocess.run(  # noqa: E731
        ["git", *args], cwd=path, check=True, capture_output=True
    )
    run("init", "--quiet", "--initial-branch", branch)
    run("config", "user.email", "test@example.invalid")
    run("config", "user.name", "Test")
    (path / "README").write_text("hello")
    run("add", "README")
    run("commit", "--quiet", "-m", "initial")
    return f"file://{path}"
