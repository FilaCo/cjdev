"""`cjdev status`, end to end against a real git.

Real repositories in a `tmp_path` for the same reason `init` uses them: what
`git worktree list --porcelain` prints for a detached checkout, and what
`rev-list --left-right` does when a remote has never heard of a branch, are
exactly the facts a fake would have to invent.
"""

import subprocess
from pathlib import Path

import pytest

from cjdev.application.report_status import ReportStatus
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Manifest, Project, ProjectRole
from cjdev.infra.executor.host import HostExecutor
from cjdev.infra.git import provision_object_store, read_store
from conftest import make_upstream

pytestmark = pytest.mark.usefixtures("git_available")


@pytest.fixture
def manifest(tmp_path: Path) -> Manifest:
    return Manifest(
        schema_version=1,
        projects=(
            Project(
                "alpha",
                ProjectRole.BUILDABLE,
                make_upstream(tmp_path / "remote" / "alpha"),
                "main",
            ),
            Project(
                "beta",
                ProjectRole.BUILDABLE,
                make_upstream(tmp_path / "remote" / "beta"),
                "main",
            ),
        ),
        build_units=(),
    )


@pytest.fixture
def workspace(tmp_path: Path, manifest: Manifest) -> Path:
    root = tmp_path / "ws"
    layout = WorkspaceLayout(root)
    Path(layout.bare_dir).mkdir(parents=True)
    for project in manifest.projects:
        provision_object_store(
            HostExecutor(), Path(layout.object_store(project.name)), project
        )
    return root


def report(manifest: Manifest) -> ReportStatus:
    """Wired by hand rather than through `Container`, which necessarily binds
    the bundled manifest and its gitcode URLs."""
    return ReportStatus(
        manifest=manifest,
        executor=HostExecutor(),
        read_store=read_store,
    )


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def add_worktree(root: Path, project: str, branch_set: str, *args: str) -> Path:
    store = Path(WorkspaceLayout(root).object_store(project))
    path = root / branch_set / project
    git(store, "worktree", "add", "--quiet", str(path), *args)
    return path


def commit(worktree: Path, message: str) -> None:
    (worktree / message).write_text(message)
    git(worktree, "add", "--all")
    git(
        worktree,
        "-c",
        "user.email=t@invalid",
        "-c",
        "user.name=T",
        "commit",
        "--quiet",
        "-m",
        message,
    )


class TestWhatTheWorkspaceHolds:
    def test_it_reports_the_root_it_was_asked_about(
        self, manifest: Manifest, workspace: Path
    ):
        status = report(manifest).perform(workspace, cwd=workspace)

        assert status.root == workspace

    def test_provisioned_projects_come_from_the_disk(
        self, manifest: Manifest, workspace: Path
    ):
        # A workspace's project set is what its object stores say it
        # is, so removing one has to change the report.
        store = Path(WorkspaceLayout(workspace).object_store("beta"))
        subprocess.run(["rm", "-rf", str(store)], check=True)

        status = report(manifest).perform(workspace, cwd=workspace)

        assert [(s.project, s.provisioned) for s in status.stores] == [
            ("alpha", True),
            ("beta", False),
        ]

    def test_a_store_the_manifest_never_heard_of_is_still_reported(
        self, manifest: Manifest, workspace: Path
    ):
        # Hiding a directory full of fetched objects because a manifest
        # override stopped listing it makes the report untrustworthy.
        layout = WorkspaceLayout(workspace)
        provision_object_store(
            HostExecutor(),
            Path(layout.object_store("gamma")),
            manifest.projects[0],
        )

        status = report(manifest).perform(workspace, cwd=workspace)

        assert [s.project for s in status.stores] == ["alpha", "beta", "gamma"]

    def test_a_fresh_workspace_has_no_branch_sets(
        self, manifest: Manifest, workspace: Path
    ):
        status = report(manifest).perform(workspace, cwd=workspace)

        assert status.branch_sets == ()
        assert status.active is None


class TestBranchSets:
    def test_worktrees_across_projects_form_one_branch_set(
        self, manifest: Manifest, workspace: Path
    ):
        add_worktree(workspace, "alpha", "fix-ice", "-b", "fix/ice", "upstream/main")
        add_worktree(workspace, "beta", "fix-ice", "-b", "fix/ice", "upstream/main")

        status = report(manifest).perform(workspace, cwd=workspace)

        assert len(status.branch_sets) == 1
        assert status.branch_sets[0].name == "fix/ice"
        assert [c.project for c in status.branch_sets[0].checkouts] == [
            "alpha",
            "beta",
        ]

    def test_checkouts_are_in_manifest_order_whatever_j_was(
        self, manifest: Manifest, workspace: Path
    ):
        # Six projects queried at once must not let the scheduler pick
        # the order they are printed in.
        add_worktree(workspace, "beta", "fix-ice", "-b", "fix/ice", "upstream/main")
        add_worktree(workspace, "alpha", "fix-ice", "-b", "fix/ice", "upstream/main")

        status = report(manifest).perform(workspace, cwd=workspace, jobs=4)

        assert [c.project for c in status.branch_sets[0].checkouts] == [
            "alpha",
            "beta",
        ]

    def test_a_detached_checkout_reports_no_branch(
        self, manifest: Manifest, workspace: Path
    ):
        # A project not yet enrolled sits on its pinned base ref.
        add_worktree(workspace, "alpha", "fix-ice", "--detach", "upstream/main")

        checkout = report(manifest).perform(workspace, cwd=workspace).branch_sets[0]

        assert checkout.checkouts[0].branch is None

    def test_the_active_branch_set_is_the_one_the_user_stands_in(
        self, manifest: Manifest, workspace: Path
    ):
        path = add_worktree(
            workspace, "alpha", "fix-ice", "-b", "fix/ice", "upstream/main"
        )

        status = report(manifest).perform(workspace, cwd=path)

        assert status.active == "fix/ice"

    def test_standing_in_the_root_makes_none_of_them_active(
        self, manifest: Manifest, workspace: Path
    ):
        add_worktree(workspace, "alpha", "fix-ice", "-b", "fix/ice", "upstream/main")

        assert report(manifest).perform(workspace, cwd=workspace).active is None


class TestPerProjectGitState:
    def test_a_clean_checkout_is_not_dirty(self, manifest: Manifest, workspace: Path):
        add_worktree(workspace, "alpha", "main", "-b", "main", "upstream/main")

        checkout = _only(report(manifest).perform(workspace, cwd=workspace))

        assert checkout.dirty is False
        assert len(checkout.head) == 40

    def test_a_modified_tracked_file_is_dirty(
        self, manifest: Manifest, workspace: Path
    ):
        path = add_worktree(workspace, "alpha", "main", "-b", "main", "upstream/main")
        (path / "README").write_text("changed")

        assert _only(report(manifest).perform(workspace, cwd=workspace)).dirty

    def test_an_untracked_file_alone_is_not_dirty(
        self, manifest: Manifest, workspace: Path
    ):
        # A rebase refuses to run on a dirty worktree, and an untracked scratch
        # file blocks no rebase. Reporting it as dirty would cry wolf.
        path = add_worktree(workspace, "alpha", "main", "-b", "main", "upstream/main")
        (path / "scratch.txt").write_text("notes")

        assert _only(report(manifest).perform(workspace, cwd=workspace)).dirty is False

    def test_local_commits_show_as_ahead_of_upstream(
        self, manifest: Manifest, workspace: Path
    ):
        path = add_worktree(workspace, "alpha", "main", "-b", "main", "upstream/main")
        commit(path, "work")

        tracking = _only(report(manifest).perform(workspace, cwd=workspace)).tracking

        assert [(t.remote, t.ahead, t.behind) for t in tracking] == [("upstream", 1, 0)]

    def test_a_remote_that_never_heard_of_the_branch_reports_nothing(
        self, manifest: Manifest, workspace: Path
    ):
        # Not an error, and not a pair of zeros either: "never pushed" and "in
        # sync" are different answers.
        add_worktree(workspace, "alpha", "fix-ice", "-b", "fix/ice", "upstream/main")

        assert _only(report(manifest).perform(workspace, cwd=workspace)).tracking == ()

    def test_a_detached_checkout_is_compared_against_nothing(
        self, manifest: Manifest, workspace: Path
    ):
        add_worktree(workspace, "alpha", "fix-ice", "--detach", "upstream/main")

        assert _only(report(manifest).perform(workspace, cwd=workspace)).tracking == ()


class TestOneBrokenProjectDoesNotHideTheRest:
    """Partial state is reported, never silent - and a report is the
    one thing worth finishing partially."""

    @pytest.fixture
    def broken(self, workspace: Path) -> Path:
        store = Path(WorkspaceLayout(workspace).object_store("beta"))
        subprocess.run(["rm", "-rf", str(store)], check=True)
        store.mkdir()
        (store / "HEAD").write_text("not a git repository")
        return workspace

    def test_the_failure_is_attributed_to_its_project(
        self, manifest: Manifest, broken: Path
    ):
        status = report(manifest).perform(broken, cwd=broken)

        failed = {s.project: s.error for s in status.stores if s.error is not None}
        assert list(failed) == ["beta"]
        assert "git" in failed["beta"]

    def test_the_readable_projects_are_still_reported(
        self, manifest: Manifest, broken: Path
    ):
        add_worktree(broken, "alpha", "main", "-b", "main", "upstream/main")

        status = report(manifest).perform(broken, cwd=broken)

        assert [c.project for c in status.branch_sets[0].checkouts] == ["alpha"]


class TestAStaleRegistration:
    """A worktree whose directory was removed by hand leaves a registration
    git still keeps (`prunable`), and one it refuses to enter.

    Reading it as a checkout would fail the project's whole read for want of
    one stale registration; dropping it silently would leave the report
    agreeing with a directory that is not there. So it is neither: it is
    named on its own, with the prune that clears it."""

    @pytest.fixture
    def stale(self, workspace: Path) -> Path:
        path = add_worktree(workspace, "alpha", "main", "-b", "main", "upstream/main")
        subprocess.run(["rm", "-rf", str(path.parent)], check=True)
        return workspace

    def test_the_project_still_reads_as_healthy(self, manifest: Manifest, stale: Path):
        status = report(manifest).perform(stale, cwd=stale)

        (store,) = (s for s in status.stores if s.project == "alpha")
        assert store.error is None
        assert store.provisioned

    def test_the_registration_is_reported_where_it_belongs(
        self, manifest: Manifest, stale: Path
    ):
        status = report(manifest).perform(stale, cwd=stale)

        (store,) = (s for s in status.stores if s.project == "alpha")
        (path,) = store.stale
        assert path.name == "alpha"  # the branch-set directory removed above

    def test_no_branch_set_is_reported_for_it(self, manifest: Manifest, stale: Path):
        # A branch-set row would describe a directory that is not there;
        # the registration belongs to the project, not to the set.
        status = report(manifest).perform(stale, cwd=stale)

        assert status.branch_sets == ()
        assert status.active is None

    def test_a_live_sibling_checkout_is_unaffected(
        self, manifest: Manifest, stale: Path
    ):
        # The queries that would enter the stale worktree are skipped, not
        # the ones for the rest of the store. The sibling sits at another
        # path: the registration blocks only recreating over the stale one.
        add_worktree(stale, "alpha", "other", "-b", "other", "upstream/main")

        status = report(manifest).perform(stale, cwd=stale)

        (store,) = (s for s in status.stores if s.project == "alpha")
        assert len(store.stale) == 1
        assert [c.project for c in status.branch_sets[0].checkouts] == ["alpha"]


def _only(status):
    """The single checkout of the single branch set these tests set up."""
    (branch_set,) = status.branch_sets
    (checkout,) = branch_set.checkouts
    return checkout
