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

REPOSITORY_ENV = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
)
"""`git rev-parse --local-env-vars`. git sets `GIT_DIR` for the hooks it
runs, and `pre-push` runs this suite: every repository a test builds in
`tmp_path` would otherwise be this checkout."""


@pytest.fixture(autouse=True)
def _no_repository_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in REPOSITORY_ENV:
        monkeypatch.delenv(name, raising=False)


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


@pytest.fixture(scope="session")
def container_runtime() -> str:
    """The runtime that answers, or a skip.

    A daemon is not a dependency of this suite: most of container mode is argv
    built from data and is tested without one. What is left needs a real
    runtime to mean anything, and a machine without one is not a failing
    machine.
    """
    for runtime in ("docker", "podman"):
        try:
            probe = subprocess.run([runtime, "info"], capture_output=True, check=False)
        except OSError:
            # Not installed at all, which is the ordinary shape here: a
            # missing binary and a daemon that will not answer both mean the
            # same thing to a test that needs one.
            continue
        if probe.returncode == 0:
            subprocess.run(
                [runtime, "pull", "alpine:3.20"], capture_output=True, check=True
            )
            return runtime
    pytest.skip("no container runtime is running")
