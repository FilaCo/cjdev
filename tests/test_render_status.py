"""What the status table shows, and what it deliberately does not."""

from io import StringIO
from pathlib import PurePath

from rich.console import Console

from cjdev.cli._render import render_status, status_payload
from cjdev.domain.state import (
    BranchSet,
    Checkout,
    Store,
    Tracking,
    WorkspaceStatus,
)

ROOT = PurePath("/ws")
HEAD = "4ee0b52be5aa162d0871d9cef11979191b6c6068"


def checkout(
    dirty: bool = False,
    tracking: tuple[Tracking, ...] = (),
    branch: str | None = "main",
) -> Checkout:
    return Checkout(
        project="alpha",
        path=ROOT / "main" / "alpha",
        branch=branch,
        head=HEAD,
        dirty=dirty,
        tracking=tracking,
    )


def render(
    *checkouts: Checkout,
    active: str | None = None,
    stores: tuple[Store, ...] = (Store("alpha", provisioned=True),),
) -> str:
    sink = StringIO()
    render_status(
        Console(file=sink, force_terminal=False, width=100),
        WorkspaceStatus(
            root=ROOT,
            active=active,
            stores=stores,
            branch_sets=(
                BranchSet(name="main", directory=ROOT / "main", checkouts=checkouts),
            )
            if checkouts
            else (),
        ),
    )
    return sink.getvalue()


def test_the_sha_is_abbreviated():
    # A short SHA; forty columns of hash in a table read
    # many times a day is the reason.
    assert "4ee0b52" in render(checkout())
    assert HEAD not in render(checkout())


def test_a_clean_checkout_says_nothing_beyond_where_it_is():
    output = render(checkout())

    assert "dirty" not in output
    assert "alpha" in output and "main" in output


def test_a_dirty_checkout_says_so():
    assert "dirty" in render(checkout(dirty=True))


def test_a_detached_checkout_is_labelled_rather_than_left_blank():
    assert "detached" in render(checkout(branch=None))


class TestOnlyDriftWorthActingOnIsShown:
    """An in-sync remote and a remote that never heard of the branch both mean
    "nothing to do", and six projects times two remotes of `0/0` would bury
    the one row that does need attention. `--json` carries the counts."""

    def test_drift_is_reported_with_its_remote(self):
        output = render(checkout(tracking=(Tracking("upstream", ahead=2, behind=1),)))

        assert "upstream ↑2 ↓1" in output

    def test_a_remote_in_sync_is_not_mentioned(self):
        output = render(checkout(tracking=(Tracking("upstream", 0, 0),)))

        assert "upstream" not in output

    def test_a_side_with_nothing_on_it_is_dropped(self):
        output = render(checkout(tracking=(Tracking("origin", ahead=3, behind=0),)))

        assert "origin ↑3" in output
        assert "↓" not in output


class TestTheActiveBranchSet:
    def test_it_is_marked_rather_than_coloured(self):
        # A colour is invisible in a pipe and in a CI log; a mark is not.
        assert "* main" in render(checkout(), active="main")

    def test_the_others_are_not(self):
        assert "* main" not in render(checkout(), active="fix/ice")


def test_a_workspace_with_no_branch_sets_says_how_to_make_one():
    output = render()

    assert "No branch sets yet" in output
    assert "alpha" in output  # the projects it does hold are still reported


def test_a_project_with_no_worktree_here_is_named_rather_than_omitted():
    # "Not enrolled in this branch set" and "missing from the report" read
    # identically when the row is simply absent, and only one of them is
    # something the reader should act on.
    drawn = render(
        checkout(),
        stores=(Store("alpha", provisioned=True), Store("beta", provisioned=True)),
    )

    assert "beta" in drawn
    assert "not checked out here" in drawn


def test_a_project_the_workspace_does_not_hold_is_not_named_per_branch_set():
    # It is absent from every branch set by definition, so saying so once per
    # set would be six lines telling the reader the same thing.
    drawn = render(
        checkout(),
        stores=(Store("alpha", provisioned=True), Store("beta", provisioned=False)),
    )

    assert "not checked out here" not in drawn


class TestAStaleRegistration:
    """A registration for a worktree whose directory is gone is named with
    its remedy, outside the tables - it belongs to the project, and a row in
    a branch-set table would describe a directory that is not there."""

    def test_it_is_named_with_the_prune_that_clears_it(self):
        drawn = render(
            stores=(
                Store("alpha", provisioned=True, stale=(PurePath("/ws/main/alpha"),)),
            ),
        )

        assert "~ alpha" in drawn
        assert "git worktree prune" in drawn

    def test_a_workspace_without_one_is_not_touched(self):
        assert "~" not in render(checkout())

    def test_the_json_payload_carries_the_path_and_the_remedy(self):
        payload = status_payload(
            WorkspaceStatus(
                root=ROOT,
                active=None,
                stores=(
                    Store(
                        "alpha", provisioned=True, stale=(PurePath("/ws/main/alpha"),)
                    ),
                ),
                branch_sets=(),
            )
        )

        projects = payload["projects"]
        assert isinstance(projects, list) and projects
        (project,) = projects
        stale_list = project["stale"]
        assert isinstance(stale_list, list) and stale_list
        (stale,) = stale_list
        assert stale["path"] == "/ws/main/alpha"
        assert stale["remedy"] == "git worktree prune"
