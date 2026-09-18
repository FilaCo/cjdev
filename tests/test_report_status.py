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
        manifest=lambda: manifest,
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
    agreeing with a worktree it cannot see. So it is neither: it is named on
    its own, with the command that clears it."""

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
        (registration,) = store.stale
        assert registration.path.name == "alpha"  # the branch-set dir removed above

    def test_the_remedy_is_the_full_command_against_the_store(
        self, manifest: Manifest, stale: Path
    ):
        # Runnable as printed; the why is recorded on `_stale_registration`.
        status = report(manifest).perform(stale, cwd=stale)

        (store,) = (s for s in status.stores if s.project == "alpha")
        (registration,) = store.stale
        assert registration.remedy == (
            f"git -C {WorkspaceLayout(stale).object_store('alpha')} worktree prune"
        )

    def test_the_moved_case_hint_carries_the_store_too(
        self, manifest: Manifest, stale: Path
    ):
        # The repair inside the fact is the same command for the same
        # reason: a bare `git worktree repair <its new path>` runs on
        # whatever repository the reader stands in, and does not find a
        # moved worktree even from the store - the new location must be
        # passed explicitly, and the store spelled out.
        status = report(manifest).perform(stale, cwd=stale)

        (store,) = (s for s in status.stores if s.project == "alpha")
        (registration,) = store.stale
        assert registration.fact == (
            "the directory is gone from it (if the worktree was moved rather "
            "than deleted, "
            f"`git -C {WorkspaceLayout(stale).object_store('alpha')} "
            "worktree repair <its new path>` reconnects it first)"
        )

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

    def test_a_stranger_worktree_is_not_reported_even_when_stale(
        self, manifest: Manifest, workspace: Path, tmp_path: Path
    ):
        # `branch_sets_of` drops live checkouts that are not one directory
        # under the root: this report describes the workspace, not everything
        # git knows. The same rule applies to stale registrations, or a
        # worktree linked off somewhere else would surface the moment it
        # broke - with a prune recommended over something cjdev never laid out.
        store = Path(WorkspaceLayout(workspace).object_store("alpha"))
        outside = tmp_path / "outside" / "alpha"
        git(
            store,
            "worktree",
            "add",
            "--quiet",
            str(outside),
            "-b",
            "ext",
            "upstream/main",
        )
        subprocess.run(["rm", "-rf", str(outside)], check=True)

        status = report(manifest).perform(workspace, cwd=workspace)

        (alpha,) = (s for s in status.stores if s.project == "alpha")
        assert alpha.stale == ()


class TestARegistrationWhoseDirectoryIsStillThere:
    """`prunable` does not mean the directory is gone: it fires as readily
    when only the registration broke - the checkout's `.git` file deleted,
    say - while the directory, the work in it and all, is still there.

    Calling that gone would send the reader to prune a live checkout, and
    the report would contradict itself about a directory that exists. The
    fact says what is actually wrong, and the remedy is repair - git's own
    for a registration that stopped pointing at a checkout that exists."""

    @pytest.fixture
    def displaced(self, workspace: Path) -> Path:
        path = add_worktree(workspace, "alpha", "main", "-b", "main", "upstream/main")
        (path / ".git").unlink()
        return workspace

    def test_it_is_not_called_gone(self, manifest: Manifest, displaced: Path):
        status = report(manifest).perform(displaced, cwd=displaced)

        (store,) = (s for s in status.stores if s.project == "alpha")
        (registration,) = store.stale
        assert registration.fact == (
            "the checkout is still in the directory, but the registration "
            "does not point at it"
        )

    def test_the_remedy_is_repair_not_prune(self, manifest: Manifest, displaced: Path):
        status = report(manifest).perform(displaced, cwd=displaced)

        (store,) = (s for s in status.stores if s.project == "alpha")
        (registration,) = store.stale
        assert registration.remedy == (
            f"git -C {WorkspaceLayout(displaced).object_store('alpha')} "
            f"worktree repair {displaced / 'main' / 'alpha'}"
        )

    @pytest.fixture
    def displaced_and_locked(self, workspace: Path) -> Path:
        path = add_worktree(workspace, "alpha", "main", "-b", "main", "upstream/main")
        git(
            Path(WorkspaceLayout(workspace).object_store("alpha")),
            "worktree",
            "lock",
            str(path),
        )
        (path / ".git").unlink()
        return workspace

    def test_a_locked_one_is_reported_stale_not_entered(
        self, manifest: Manifest, displaced_and_locked: Path
    ):
        # Of the deadness tests in `_dead`, only the `.git` one catches this
        # entry. Read as live, the project dies inside the checkout with
        # `not a git repository`.
        status = report(manifest).perform(
            displaced_and_locked, cwd=displaced_and_locked
        )

        (store,) = (s for s in status.stores if s.project == "alpha")
        assert store.error is None
        (registration,) = store.stale
        assert registration.fact == (
            "the checkout is still in the directory, but the registration "
            "does not point at it, and the registration is locked"
        )

    def test_a_locked_one_is_repaired_like_the_unlocked_one(
        self, manifest: Manifest, displaced_and_locked: Path
    ):
        # The same brokenness, the same remedy: repair reconnects under a
        # lock - the lock survives it - where unlock + prune would take the
        # live checkout with the registration.
        status = report(manifest).perform(
            displaced_and_locked, cwd=displaced_and_locked
        )

        (store,) = (s for s in status.stores if s.project == "alpha")
        (registration,) = store.stale
        assert registration.remedy == (
            f"git -C {WorkspaceLayout(displaced_and_locked).object_store('alpha')} "
            f"worktree repair {displaced_and_locked / 'main' / 'alpha'}"
        )


class TestALockedAndMissingWorktree:
    """A locked worktree whose directory is gone is dead for `_dead` but
    invisible to `prunable` - the lock suppresses it (the why is recorded
    on `Linked.locked`), so without the `is_dir` test the crash this fix is
    about would survive for exactly the entries a user tried to protect.

    It is reported stale with unlock + prune as the remedy; the fact
    carries the repair the moved case needs first (why, see
    `_stale_registration`)."""

    @pytest.fixture
    def locked_and_missing(self, workspace: Path) -> Path:
        path = add_worktree(workspace, "alpha", "main", "-b", "main", "upstream/main")
        git(
            Path(WorkspaceLayout(workspace).object_store("alpha")),
            "worktree",
            "lock",
            str(path),
        )
        subprocess.run(["rm", "-rf", str(path.parent)], check=True)
        return workspace

    def test_it_is_reported_stale_not_entered(
        self, manifest: Manifest, locked_and_missing: Path
    ):
        status = report(manifest).perform(locked_and_missing, cwd=locked_and_missing)

        (store,) = (s for s in status.stores if s.project == "alpha")
        assert store.error is None
        (registration,) = store.stale
        assert registration.fact == (
            "the directory is gone from it, and the registration is locked "
            "(if the worktree was moved rather than deleted, "
            f"`git -C {WorkspaceLayout(locked_and_missing).object_store('alpha')} "
            "worktree repair <its new path>` reconnects it first)"
        )
        assert registration.remedy == (
            f"git -C {WorkspaceLayout(locked_and_missing).object_store('alpha')} "
            f"worktree unlock {locked_and_missing / 'main' / 'alpha'} && "
            f"git -C {WorkspaceLayout(locked_and_missing).object_store('alpha')} "
            "worktree prune"
        )


def _only(status):
    """The single checkout of the single branch set these tests set up."""
    (branch_set,) = status.branch_sets
    (checkout,) = branch_set.checkouts
    return checkout
