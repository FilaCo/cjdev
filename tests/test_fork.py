"""Deriving a fork's URL, and deciding commits and pushes, with nothing on disk."""

from pathlib import PurePath

import pytest

from cjdev.application.commit_branch_set import Pending
from cjdev.application.commit_branch_set import decide as decide_commit
from cjdev.application.push_branch_set import Push, Skip, Unpushed
from cjdev.application.push_branch_set import decide as decide_push
from cjdev.application.wire_origin import Remotes, Wiring
from cjdev.application.wire_origin import decide as decide_origin
from cjdev.domain.fork import fork_url, web_page
from cjdev.errors import PreconditionError, UsageError

UPSTREAM = "https://gitcode.com/Cangjie/cangjie_compiler.git"
FORK = "https://gitcode.com/filaco/cangjie_compiler.git"


@pytest.mark.parametrize(
    ("upstream", "fork"),
    [
        (UPSTREAM, FORK),
        ("git@gitcode.com:Cangjie/stdx.git", "git@gitcode.com:filaco/stdx.git"),
        ("file:///srv/git/Cangjie/stdx", "file:///srv/git/filaco/stdx"),
    ],
)
def test_the_namespace_is_replaced_and_the_rest_kept(upstream: str, fork: str):
    # Act / Assert
    assert fork_url(upstream, "filaco") == fork


def test_a_url_with_no_namespace_has_no_fork():
    # Act / Assert
    with pytest.raises(PreconditionError):
        fork_url("https://gitcode.com/cangjie_compiler.git", "filaco")


@pytest.mark.parametrize("owner", ["", "a/b", "evil.com:x", "-flag"])
def test_an_owner_that_would_change_the_host_or_path_is_refused(owner: str):
    # Act / Assert
    with pytest.raises(UsageError):
        fork_url(UPSTREAM, owner)


def test_the_web_page_of_an_ssh_remote_is_its_https_one():
    # Act / Assert
    assert (
        web_page("git@gitcode.com:filaco/stdx.git") == "https://gitcode.com/filaco/stdx"
    )
    assert web_page("file:///srv/git/filaco/stdx") is None


def remotes(origin: str | None) -> Remotes:
    return Remotes("cangjie_compiler", PurePath("s"), UPSTREAM, origin)


def test_an_origin_that_disagrees_is_kept():
    # Arrange
    elsewhere = "https://gitcode.com/filaco/compiler-fork.git"

    # Act
    wires = decide_origin("filaco", [remotes(None), remotes(FORK), remotes(elsewhere)])

    # Assert
    assert [w.wiring for w in wires] == [Wiring.ADD, Wiring.PRESENT, Wiring.DISAGREES]
    assert wires[2].existing == elsewhere


def pending(project: str, *, changes: bool, branch: str | None = "fix") -> Pending:
    return Pending(project, PurePath(project), branch, "main", changes)


def test_a_clean_project_on_the_default_branch_does_not_block_the_commit():
    # Arrange
    projects = [pending("a", changes=True), pending("b", changes=False, branch="main")]

    # Act
    plan = decide_commit(projects)

    # Assert
    assert [p.project for p in plan.to_commit] == ["a"]


@pytest.mark.parametrize("branch", ["main", None])
def test_a_commit_off_a_branch_set_branch_is_refused(branch: str | None):
    # Act / Assert
    with pytest.raises(PreconditionError):
        decide_commit([pending("a", changes=True, branch=branch)])


def test_only_narrows_and_rejects_a_stranger():
    # Arrange
    projects = [pending("a", changes=True), pending("b", changes=True)]

    # Act
    plan = decide_commit(projects, ["b"])

    # Assert
    assert [p.project for p in plan.to_commit] == ["b"]
    with pytest.raises(UsageError):
        decide_commit(projects, ["c"])


def unpushed(**changes: object) -> Unpushed:
    fields: dict[str, object] = {
        "project": "a",
        "worktree": PurePath("a"),
        "branch": "fix",
        "default_branch": "main",
        "upstream_url": UPSTREAM,
        "origin_url": FORK,
        "origin_head": None,
        "ahead": 1,
        "behind": 0,
        "tracked": False,
    }
    fields.update(changes)
    return Unpushed(**fields)  # type: ignore[arg-type]


def test_the_first_push_sets_tracking():
    # Act
    (step,) = decide_push([unpushed()]).steps

    # Assert
    assert isinstance(step, Push)
    assert step.set_upstream
    assert step.lease is None


def test_a_branch_with_nothing_of_its_own_is_skipped():
    # Act
    (step,) = decide_push([unpushed(ahead=0)]).steps

    # Assert
    assert isinstance(step, Skip)


@pytest.mark.parametrize(
    "state",
    [
        {"origin_url": None},
        # Upstream is read-only: an origin pointing there is still upstream.
        {"origin_url": UPSTREAM},
        {"branch": "main"},
        {"origin_head": "abc", "behind": 2},
    ],
)
def test_a_push_that_would_land_wrong_is_refused(state: dict[str, object]):
    # Act / Assert
    with pytest.raises(PreconditionError):
        decide_push([unpushed(**state)])


def test_a_rewrite_goes_out_only_with_the_lease_pinned_to_what_was_seen():
    # Act
    (step,) = decide_push(
        [unpushed(origin_head="abc", behind=2, tracked=True)], force=True
    ).steps

    # Assert
    assert isinstance(step, Push)
    assert step.lease == "abc"
    assert not step.set_upstream
