"""`cjdev branch new`: the decision, and then the same command against git.

The decision is asserted with no repository in sight. The undo is not: it is
built on `worktree add -b` creating a branch before it fails and `worktree
remove` keeping one, which only the real binary can be trusted about.
"""

import subprocess
import threading
from pathlib import Path, PurePath
from typing import final

import pytest

from cjdev.application.new_branch_set import (
    Action,
    Enrolment,
    Held,
    NewBranchSet,
    Observed,
    decide,
    report_rows,
)
from cjdev.application.ports import Command, Completed, Executor
from cjdev.application.runner import Outcome, RunReport, UnitResult
from cjdev.domain.branch import check_branch_name
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Manifest, Project, ProjectRole
from cjdev.errors import PreconditionError, UsageError
from cjdev.infra.executor import build_executor
from cjdev.infra.executor.host import HostExecutor
from cjdev.infra.filesystem import HostFileSystem, build_file_system
from cjdev.infra.git import (
    add_checkout,
    drop_checkout,
    inspect_checkout,
    provision_object_store,
)
from conftest import make_upstream

pytestmark = pytest.mark.usefixtures("git_available")

LAYOUT = WorkspaceLayout(PurePath("/ws"))
MAIN = "refs/remotes/upstream/main"
TRUNK = "refs/remotes/upstream/trunk"


def held(
    project: str,
    *,
    base: str | None = MAIN,
    branch_exists: bool = False,
    checked_out: str | None = None,
    elsewhere: PurePath | None = None,
    occupied: bool = False,
) -> Held:
    return Held(
        project=project,
        base=base,
        branch_exists=branch_exists,
        checked_out=checked_out,
        elsewhere=elsewhere,
        occupied=occupied,
    )


def observed(*projects: Held, directory_exists: bool = False) -> Observed:
    return Observed(projects=projects, directory_exists=directory_exists)


def branch_set(manifest: Manifest, **overrides: object) -> NewBranchSet:
    """Wired by hand rather than through `Container`, which necessarily binds
    the bundled manifest and its gitcode URLs."""
    wiring: dict[str, object] = {
        "manifest": manifest,
        "executor": HostExecutor(),
        "file_system": HostFileSystem(),
        "inspect": inspect_checkout,
        "add": add_checkout,
        "drop": drop_checkout,
    }
    wiring.update(overrides)
    return NewBranchSet(**wiring)  # type: ignore[arg-type]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def store_of(root: Path, project: str) -> Path:
    return Path(WorkspaceLayout(root).object_store(project))


@pytest.fixture
def manifest(tmp_path: Path) -> Manifest:
    # The two projects disagree about their default branch, or nothing here
    # would notice a hardcoded `main`.
    return Manifest(
        schema_version=1,
        projects=(
            Project(
                name="alpha",
                role=ProjectRole.BUILDABLE,
                upstream_url=make_upstream(tmp_path / "upstreams" / "alpha"),
                default_branch="main",
            ),
            Project(
                name="beta",
                role=ProjectRole.BUILDABLE,
                upstream_url=make_upstream(
                    tmp_path / "upstreams" / "beta", branch="trunk"
                ),
                default_branch="trunk",
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


class TestDecide:
    """The pure half. No filesystem, no git."""

    def test_the_set_covers_every_project_the_workspace_holds(self):
        # Arrange
        seen = observed(held("alpha"), held("beta"))

        # Act
        plan = decide(LAYOUT, "fix/ice", seen)

        # Assert
        assert [e.project for e in plan.enrolments] == ["alpha", "beta"]
        assert all(e.action is Action.CREATE for e in plan.enrolments)

    def test_every_checkout_lands_under_one_directory_named_for_the_branch(self):
        # Arrange
        seen = observed(held("alpha"), held("beta"))

        # Act
        plan = decide(LAYOUT, "fix/ice", seen)

        # Assert
        assert plan.directory == PurePath("/ws/fix-ice")
        assert [e.worktree for e in plan.enrolments] == [
            PurePath("/ws/fix-ice/alpha"),
            PurePath("/ws/fix-ice/beta"),
        ]

    def test_each_project_starts_from_its_own_recorded_default_branch(self):
        # Arrange
        seen = observed(held("alpha"), held("beta", base=TRUNK))

        # Act
        plan = decide(LAYOUT, "fix/ice", seen)

        # Assert
        assert [e.base for e in plan.enrolments] == [MAIN, TRUNK]

    def test_the_branch_keeps_the_name_the_user_gave(self):
        # Arrange
        seen = observed(held("alpha"))

        # Act
        plan = decide(LAYOUT, "fix/ice", seen)

        # Assert: flattening is one-way, so the directory is a label and the
        # branch is the identity.
        assert plan.branch == "fix/ice"
        assert plan.enrolments[0].branch == "fix/ice"

    def test_a_branch_that_already_exists_is_adopted(self):
        # Arrange
        seen = observed(held("alpha", branch_exists=True))

        # Act
        plan = decide(LAYOUT, "fix/ice", seen)

        # Assert: adopting takes the branch where it is, so there is no base
        # to reset it onto.
        assert plan.enrolments[0].action is Action.ADOPT
        assert plan.enrolments[0].base is None

    def test_a_checkout_already_on_the_name_is_left_alone(self):
        # Arrange
        seen = observed(held("alpha", branch_exists=True, checked_out="fix/ice"))

        # Act
        plan = decide(LAYOUT, "fix/ice", seen)

        # Assert
        assert plan.enrolments[0].action is Action.PRESENT
        assert plan.to_enrol == ()
        assert plan.is_noop

    def test_a_partial_set_is_completed(self):
        # Arrange
        seen = observed(
            held("alpha", branch_exists=True, checked_out="fix/ice"),
            held("beta"),
            directory_exists=True,
        )

        # Act
        plan = decide(LAYOUT, "fix/ice", seen)

        # Assert
        assert [(e.project, e.action) for e in plan.enrolments] == [
            ("alpha", Action.PRESENT),
            ("beta", Action.CREATE),
        ]

    def test_a_directory_holding_another_branch_set_is_refused_by_name(self):
        # Arrange: `fix/ice` and `fix-ice` flatten to one directory.
        seen = observed(held("alpha", checked_out="fix/ice"), directory_exists=True)

        # Act / Assert
        with pytest.raises(PreconditionError, match="fix/ice") as refused:
            decide(LAYOUT, "fix-ice", seen)
        assert "alpha" in str(refused.value)

    def test_a_directory_with_something_else_in_it_is_refused(self):
        # Arrange
        seen = observed(held("alpha", occupied=True), directory_exists=True)

        # Act / Assert
        with pytest.raises(PreconditionError, match="not empty"):
            decide(LAYOUT, "fix/ice", seen)

    def test_a_branch_already_checked_out_elsewhere_is_refused(self):
        # Arrange: git allows one worktree per branch, so the adopt would fail
        # mid-run.
        seen = observed(
            held("alpha", branch_exists=True, elsewhere=PurePath("/ws/elsewhere/alpha"))
        )

        # Act / Assert
        with pytest.raises(PreconditionError, match="elsewhere/alpha"):
            decide(LAYOUT, "fix/ice", seen)

    def test_a_project_with_no_recorded_default_branch_names_the_fix(self):
        # Arrange
        seen = observed(held("alpha", base=None))

        # Act / Assert
        with pytest.raises(PreconditionError) as refused:
            decide(LAYOUT, "fix/ice", seen)
        assert "cjdev init" in (refused.value.remedy or "")

    def test_a_name_git_would_refuse_decides_nothing(self):
        # Arrange
        seen = observed(held("alpha"))

        # Act / Assert
        with pytest.raises(UsageError):
            decide(LAYOUT, "fix/../escape", seen)


class TestBranchNames:
    @pytest.mark.parametrize(
        "name",
        [
            "",
            "fix/../escape",
            "../escape",
            ".hidden",
            "/leading",
            "trailing/",
            "a//b",
            "with space",
            "tilde~1",
            "caret^",
            "colon:",
            "question?",
            "star*",
            "bracket[",
            "back\\slash",
            "at@{1}",
            "@",
            "trailing.",
            "feature.lock",
            "-dash",
            "control\tchar",
        ],
    )
    def test_it_is_refused(self, name: str):
        # Act / Assert
        with pytest.raises(UsageError):
            check_branch_name(name)

    @pytest.mark.parametrize("name", ["main", "fix/parser-ice", "a/b/c", "v1.2.x"])
    def test_an_ordinary_name_is_accepted(self, name: str):
        # Act / Assert
        assert check_branch_name(name) == name

    @pytest.mark.parametrize(
        "name",
        ["main", "fix/parser-ice", "a/b/c", "v1.2.x", "with space", "tilde~1", "a//b"],
    )
    def test_it_agrees_with_git_itself(self, name: str):
        # Arrange: `refs/heads/` rather than `--branch`, which also resolves
        # shorthands like `@{-1}` against a repository.
        theirs = subprocess.run(
            ["git", "check-ref-format", f"refs/heads/{name}"], capture_output=True
        ).returncode

        # Act
        ours = True
        try:
            check_branch_name(name)
        except UsageError:
            ours = False

        # Assert
        assert ours == (theirs == 0)


class TestReportRows:
    def test_a_project_the_run_never_reached_does_not_read_as_done(self):
        # Arrange: alpha failed, so beta was cancelled and has no checkout.
        plan = decide(LAYOUT, "fix/ice", observed(held("alpha"), held("beta")))
        report: RunReport[Enrolment] = RunReport(
            (UnitResult("alpha", Outcome.FAILED, error=RuntimeError("no")),)
        )

        # Act
        rows = report_rows(plan, report)

        # Assert
        assert [row.outcome for row in rows] == [Outcome.FAILED, Outcome.CANCELLED]

    def test_rows_follow_the_plan_rather_than_the_finish_order(self):
        # Arrange
        plan = decide(LAYOUT, "fix/ice", observed(held("alpha"), held("beta")))
        report: RunReport[Enrolment] = RunReport(
            (
                UnitResult("beta", Outcome.DONE),
                UnitResult("alpha", Outcome.FAILED, error=RuntimeError("no")),
            )
        )

        # Act
        rows = report_rows(plan, report)

        # Assert
        assert [row.project for row in rows] == ["alpha", "beta"]
        assert [row.outcome for row in rows] == [Outcome.FAILED, Outcome.DONE]

    def test_a_project_that_was_already_there_is_reported_too(self):
        # Arrange: it runs no work, so it appears in no run report.
        plan = decide(
            LAYOUT,
            "fix/ice",
            observed(held("alpha", branch_exists=True, checked_out="fix/ice")),
        )

        # Act
        rows = report_rows(plan, RunReport(()))

        # Assert
        assert [(r.project, r.action) for r in rows] == [("alpha", Action.PRESENT)]
        assert rows[0].outcome is Outcome.DONE


class TestPreconditions:
    def test_a_workspace_with_no_projects_names_the_fix(
        self, tmp_path: Path, manifest: Manifest
    ):
        # Arrange
        root = tmp_path / "empty"
        Path(WorkspaceLayout(root).marker).mkdir(parents=True)

        # Act / Assert
        with pytest.raises(PreconditionError) as refused:
            branch_set(manifest).plan(root, "fix/ice")
        assert "cjdev init" in (refused.value.remedy or "")


class TestEndToEnd:
    def test_every_project_gets_a_checkout_on_the_name(
        self, workspace: Path, manifest: Manifest
    ):
        # Act
        report = branch_set(manifest).perform(workspace, "fix/ice", jobs=2)

        # Assert
        assert report.ok, [str(row.error) for row in report.rows]
        for project in ("alpha", "beta"):
            worktree = workspace / "fix-ice" / project
            assert (worktree / "README").is_file()
            assert git(worktree, "rev-parse", "--abbrev-ref", "HEAD") == "fix/ice"

    def test_each_checkout_starts_from_the_projects_own_default_branch(
        self, workspace: Path, manifest: Manifest, tmp_path: Path
    ):
        # Arrange: beta's default branch is `trunk`.
        upstream = tmp_path / "upstreams" / "beta"

        # Act
        branch_set(manifest).perform(workspace, "fix/ice", jobs=2)

        # Assert
        assert git(workspace / "fix-ice" / "beta", "rev-parse", "HEAD") == git(
            upstream, "rev-parse", "trunk"
        )

    def test_the_branch_is_not_wired_to_push_at_the_read_only_upstream(
        self, workspace: Path, manifest: Manifest
    ):
        # Arrange: the base is a remote-tracking ref, and git would set up
        # tracking against it by default.
        worktree = workspace / "fix-ice" / "alpha"

        # Act
        branch_set(manifest).perform(workspace, "fix/ice", jobs=2)

        # Assert
        tracked = subprocess.run(
            ["git", "config", "--get", "branch.fix/ice.remote"],
            cwd=worktree,
            capture_output=True,
        )
        assert tracked.returncode != 0

    def test_running_it_again_reports_the_set_as_already_present(
        self, workspace: Path, manifest: Manifest
    ):
        # Arrange
        use_case = branch_set(manifest)
        use_case.perform(workspace, "fix/ice", jobs=2)

        # Act
        again = use_case.perform(workspace, "fix/ice", jobs=2)

        # Assert
        assert again.ok
        assert [row.action for row in again.rows] == [Action.PRESENT] * 2

    def test_a_branch_left_from_an_earlier_set_is_adopted_with_its_commits(
        self, workspace: Path, manifest: Manifest
    ):
        # Arrange: `worktree remove` keeps the branch, so last week's work is
        # still on it.
        use_case = branch_set(manifest)
        use_case.perform(workspace, "fix/ice", jobs=2)
        worktree = workspace / "fix-ice" / "alpha"
        (worktree / "work").write_text("in progress")
        git(worktree, "add", "work")
        git(
            worktree,
            "-c",
            "user.email=t@e.invalid",
            "-c",
            "user.name=T",
            "commit",
            "-qm",
            "wip",
        )
        done = git(worktree, "rev-parse", "HEAD")
        git(store_of(workspace, "alpha"), "worktree", "remove", str(worktree))

        # Act
        report = branch_set(manifest).perform(workspace, "fix/ice", jobs=2)

        # Assert
        assert report.ok
        assert [row.action for row in report.rows] == [Action.ADOPT, Action.PRESENT]
        assert git(worktree, "rev-parse", "HEAD") == done
        assert (worktree / "work").is_file()

    def test_a_project_added_to_the_workspace_later_joins_the_set(
        self, workspace: Path, manifest: Manifest, tmp_path: Path
    ):
        # Arrange
        branch_set(manifest).perform(workspace, "fix/ice", jobs=2)
        gamma = Project(
            name="gamma",
            role=ProjectRole.BUILDABLE,
            upstream_url=make_upstream(tmp_path / "upstreams" / "gamma"),
            default_branch="main",
        )
        provision_object_store(HostExecutor(), store_of(workspace, "gamma"), gamma)
        grown = Manifest(
            schema_version=1, projects=(*manifest.projects, gamma), build_units=()
        )

        # Act
        report = branch_set(grown).perform(workspace, "fix/ice", jobs=2)

        # Assert
        assert report.ok
        assert [(row.project, row.action) for row in report.rows] == [
            ("alpha", Action.PRESENT),
            ("beta", Action.PRESENT),
            ("gamma", Action.CREATE),
        ]

    def test_two_projects_can_be_in_flight_at_once(
        self, workspace: Path, manifest: Manifest
    ):
        # Arrange: the barrier only opens with both units inside it.
        gate = threading.Barrier(2, timeout=5)

        def add(executor: Executor, enrolment: Enrolment) -> None:
            gate.wait()
            add_checkout(executor, enrolment)

        # Act
        report = branch_set(manifest, add=add).perform(workspace, "fix/ice", jobs=2)

        # Assert
        assert report.ok, [str(row.error) for row in report.rows]


class TestAFailedRunLeavesNothingBehind:
    def test_it_removes_the_checkout_and_the_branch_it_created(
        self, workspace: Path, manifest: Manifest
    ):
        # Arrange: one job, so alpha is the one that got done and beta is the
        # failure, rather than that being the scheduler's call.
        def add(executor: Executor, enrolment: Enrolment) -> None:
            if enrolment.project == "beta":
                raise RuntimeError("disk full")
            add_checkout(executor, enrolment)

        # Act
        report = branch_set(manifest, add=add).perform(workspace, "fix/ice", jobs=1)

        # Assert
        assert not report.ok
        assert not (workspace / "fix-ice").exists()
        assert git(store_of(workspace, "alpha"), "branch", "--list", "fix/ice") == ""

    def test_it_deletes_the_branch_a_failed_worktree_add_left_behind(
        self, workspace: Path, manifest: Manifest
    ):
        # Arrange: with `-b` the branch is created before the checkout is
        # attempted, so a failure at the checkout orphans it.
        def add(executor: Executor, enrolment: Enrolment) -> None:
            if enrolment.project == "beta":
                Path(enrolment.worktree).mkdir(parents=True)
                (Path(enrolment.worktree) / "junk").write_text("in the way")
            add_checkout(executor, enrolment)

        # Act
        report = branch_set(manifest, add=add).perform(workspace, "fix/ice", jobs=1)

        # Assert
        assert not report.ok
        for project in ("alpha", "beta"):
            store = store_of(workspace, project)
            assert git(store, "branch", "--list", "fix/ice") == ""
        # The file in the way is the user's, not ours.
        assert (workspace / "fix-ice" / "beta" / "junk").is_file()

    def test_it_keeps_the_checkouts_and_branches_it_did_not_create(
        self, workspace: Path, manifest: Manifest
    ):
        # Arrange: alpha is checked out and dirty, beta's branch exists with
        # no worktree.
        branch_set(manifest).perform(workspace, "fix/ice", jobs=2)
        worktree = workspace / "fix-ice" / "alpha"
        (worktree / "scratch").write_text("uncommitted")
        git(
            store_of(workspace, "beta"),
            "worktree",
            "remove",
            str(workspace / "fix-ice" / "beta"),
        )

        def add(executor: Executor, enrolment: Enrolment) -> None:
            raise RuntimeError("disk full")

        # Act
        report = branch_set(manifest, add=add).perform(workspace, "fix/ice", jobs=1)

        # Assert
        assert not report.ok
        assert (worktree / "scratch").read_text() == "uncommitted"
        assert git(store_of(workspace, "beta"), "branch", "--list", "fix/ice") != ""

    def test_a_second_run_cannot_delete_what_the_first_one_created(
        self, workspace: Path, manifest: Manifest, tmp_path: Path
    ):
        # Arrange: the set exists, beta is back to a branch with no worktree,
        # and a newly held project is about to fail. The branch a run may
        # delete is only one it decided to create, so beta's - created by the
        # first run and adopted by the second - is out of reach.
        branch_set(manifest).perform(workspace, "fix/ice", jobs=2)
        git(
            store_of(workspace, "beta"),
            "worktree",
            "remove",
            str(workspace / "fix-ice" / "beta"),
        )
        gamma = Project(
            name="gamma",
            role=ProjectRole.BUILDABLE,
            upstream_url=make_upstream(tmp_path / "upstreams" / "gamma"),
            default_branch="main",
        )
        provision_object_store(HostExecutor(), store_of(workspace, "gamma"), gamma)
        grown = Manifest(
            schema_version=1, projects=(*manifest.projects, gamma), build_units=()
        )

        def add(executor: Executor, enrolment: Enrolment) -> None:
            if enrolment.project == "gamma":
                raise RuntimeError("disk full")
            add_checkout(executor, enrolment)

        # Act
        report = branch_set(grown, add=add).perform(workspace, "fix/ice", jobs=1)

        # Assert
        assert not report.ok
        assert git(store_of(workspace, "alpha"), "branch", "--list", "fix/ice") != ""
        assert git(store_of(workspace, "beta"), "branch", "--list", "fix/ice") != ""
        assert git(store_of(workspace, "gamma"), "branch", "--list", "fix/ice") == ""
        assert (workspace / "fix-ice" / "alpha" / "README").is_file()

    def test_the_undo_runs_through_the_executor_that_records_it(
        self, workspace: Path, manifest: Manifest
    ):
        # Arrange: the workspace log is written from the executor, so an undo
        # that went around it would run unrecorded.
        recorded: list[tuple[str, ...]] = []

        @final
        class Recorder:
            def run(self, command: Command, *, check: bool = True) -> Completed:
                recorded.append(command.argv)
                return HostExecutor().run(command, check=check)

        def add(executor: Executor, enrolment: Enrolment) -> None:
            if enrolment.project == "beta":
                raise RuntimeError("disk full")
            add_checkout(executor, enrolment)

        # Act
        branch_set(manifest, add=add, executor=Recorder()).perform(
            workspace, "fix/ice", jobs=1
        )

        # Assert
        alpha = str(workspace / "fix-ice" / "alpha")
        assert ("git", "worktree", "remove", "--force", alpha) in recorded
        assert ("git", "branch", "-D", "fix/ice") in recorded


class TestDryRun:
    def test_it_changes_nothing_at_all(self, workspace: Path, manifest: Manifest):
        # Arrange
        printed: list[str] = []
        use_case = branch_set(
            manifest,
            executor=build_executor(dry_run=True, emit=printed.append),
            file_system=build_file_system(dry_run=True, emit=printed.append),
        )

        # Act
        use_case.perform(workspace, "fix/ice", jobs=2, dry_run=True)

        # Assert
        assert not (workspace / "fix-ice").exists()

    def test_it_prints_the_commands_it_would_run(
        self, workspace: Path, manifest: Manifest
    ):
        # Arrange
        printed: list[str] = []
        use_case = branch_set(
            manifest,
            executor=build_executor(dry_run=True, emit=printed.append),
            file_system=build_file_system(dry_run=True, emit=printed.append),
        )

        # Act
        use_case.perform(workspace, "fix/ice", jobs=2, dry_run=True)

        # Assert
        added = [line for line in printed if "worktree add" in line]
        assert len(added) == 2
        assert str(workspace / "fix-ice" / "alpha") in added[0]
