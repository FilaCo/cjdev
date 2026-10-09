"""`cjdev test`: the framework, inside the build environment, against the
branch set's own dist.

The two ways this went wrong by hand were both the dist - a profile never
fully built, and `CANGJIE_HOME` pointing at the other profile's SDK - so most
of what is asserted here is which SDK a run sees.
"""

from pathlib import Path, PurePath
from typing import final

import pytest

from cjdev.application.ports import Command, Completed
from cjdev.application.run_tests import RunTests, classify, decide
from cjdev.domain.build import Host, Profile
from cjdev.domain.environment import Environment, Mode
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.testing import Suite
from cjdev.errors import PreconditionError, UsageError

ROOT = PurePath("/ws")
TESTS = ROOT / "main" / "cangjie_test"
LLT = TESTS / "testsuites" / "LLT"
HLT = TESTS / "testsuites" / "HLT"
HOST = Host(
    target="linux_x86_64",
    jobs=8,
    path="/usr/bin",
    library_var="LD_LIBRARY_PATH",
    library_path="",
    ccache=None,
)
RESULTS = (Path(__file__).parent / "data" / "framework_results.json").read_text()


@final
class FakeExecutor:
    def __init__(self, exit_code: int = 0) -> None:
        self.ran: list[Command] = []
        self._exit_code = exit_code

    def run(self, command: Command, *, check: bool = True) -> Completed:
        self.ran.append(command)
        return Completed(command, self._exit_code, "", "")


@final
class FakeFileSystem:
    def __init__(self) -> None:
        self.made: list[PurePath] = []
        self.removed: list[PurePath] = []

    def mkdir(self, path: PurePath) -> None:
        self.made.append(path)

    def write_text(self, path: PurePath, text: str) -> None: ...

    def remove(self, path: PurePath) -> None:
        self.removed.append(path)

    def symlink(self, link: PurePath, target: PurePath) -> None: ...

    def copy(self, source: PurePath, into: PurePath) -> None: ...

    def move(self, source: PurePath, destination: PurePath) -> None: ...


def plan_for(
    suites: dict[Suite, tuple[PurePath, ...]],
    *,
    profile: Profile = Profile.DEBUG,
    mode: Mode = Mode.HOST,
    passthrough: tuple[str, ...] = (),
):
    return decide(
        WorkspaceLayout(ROOT),
        "main",
        profile,
        HOST,
        suites,
        cwd=ROOT / "main",
        environment=Environment(mode),
        passthrough=passthrough,
    )


class TestClassify:
    def test_each_path_goes_to_the_suite_it_sits_in(self):
        # Act
        suites = classify(TESTS, [LLT / "compiler" / "a.cj", HLT / "API", LLT])

        # Assert
        assert suites == {
            Suite.LLT: (LLT / "compiler" / "a.cj", LLT),
            Suite.HLT: (HLT / "API",),
        }

    def test_a_path_outside_both_suites_has_nothing_to_run_it_with(self):
        # Act / Assert
        with pytest.raises(UsageError, match="not inside"):
            classify(TESTS, [ROOT / "main" / "cangjie_compiler"])


class TestDecide:
    def test_the_run_sees_the_profile_s_own_sdk(self):
        # Act
        command = plan_for({Suite.LLT: (LLT,)}).runs[0].command

        # Assert
        assert command.env["CANGJIE_HOME"] == "/ws/.cjdev/dist/main/host/debug"
        assert command.env["CANGJIE_TEST"] == str(TESTS)

    def test_the_suite_and_host_choose_the_list_and_config(self):
        # Act
        argv = plan_for({Suite.LLT: (LLT,)}).runs[0].command.argv

        # Assert
        assert argv[argv.index("--test_cfg") + 1] == str(
            LLT / "configs/cjnative/cjnative_test.cfg"
        )
        assert argv[argv.index("--test_list") + 1] == str(LLT / "cjnative_testlist")

    def test_scratch_and_logs_stay_out_of_the_framework_s_worktree(self):
        # Act
        argv = plan_for({Suite.HLT: (HLT,)}).runs[0].command.argv

        # Assert
        scratch = "/ws/.cjdev/build/main/test/host/debug/HLT"
        assert argv[argv.index("--temp_dir") + 1] == f"{scratch}/run"
        assert argv[argv.index("--log_dir") + 1] == f"{scratch}/log"
        assert argv[argv.index("--json_output") + 1] == f"{scratch}/results.json"

    def test_only_failures_are_printed_and_with_their_output(self):
        # Act
        argv = plan_for({Suite.LLT: (LLT,)}).runs[0].command.argv

        # Assert
        assert "-pFAIL" in argv
        assert "--fail-verbose" in argv

    def test_the_caller_s_arguments_come_last_so_theirs_win(self):
        # Act
        argv = (
            plan_for({Suite.LLT: (LLT,)}, passthrough=("-j", "2")).runs[0].command.argv
        )

        # Assert: argparse keeps the last of a repeated option.
        assert argv[-3:] == (str(LLT), "-j", "2")
        assert argv.index("-j") < len(argv) - 2

    def test_one_run_per_suite(self):
        # Act
        plan = plan_for({Suite.LLT: (LLT / "a",), Suite.HLT: (HLT / "b",)})

        # Assert
        assert [run.suite for run in plan.runs] == [Suite.LLT, Suite.HLT]

    def test_the_terminal_is_the_caller_s_while_it_runs(self):
        # Act
        command = plan_for({Suite.LLT: (LLT,)}).runs[0].command

        # Assert: a run of thousands of cases is watched, and the summary
        # comes from the results file rather than from captured output.
        assert command.interactive

    def test_a_container_workspace_tests_the_container_s_dist(self):
        # Act
        command = plan_for({Suite.LLT: (LLT,)}, mode=Mode.CONTAINER).runs[0].command

        # Assert
        assert command.env["CANGJIE_HOME"] == "/ws/.cjdev/dist/main/container/debug"


class TestPlan:
    @pytest.fixture
    def root(self, tmp_path: Path) -> Path:
        layout = WorkspaceLayout(tmp_path)
        Path(layout.worktree("main", "cangjie_test_framework")).mkdir(parents=True)
        Path(layout.worktree("main", "cangjie_test") / "testsuites/LLT/x").mkdir(
            parents=True
        )
        Path(layout.dist_dir("main", "host", "debug")).mkdir(parents=True)
        return tmp_path

    def use_case(self) -> RunTests:
        return RunTests(
            executor=FakeExecutor(),
            file_system=FakeFileSystem(),
            host=lambda: HOST,
            read_results=lambda _: None,
        )

    def test_a_profile_never_built_is_a_refusal_not_a_thousand_failures(
        self, root: Path
    ):
        # Act / Assert
        with pytest.raises(PreconditionError) as refusal:
            self.use_case().plan(
                root,
                "main",
                profile=Profile.RELEASE,
                paths=[root / "main/cangjie_test/testsuites/LLT/x"],
                cwd=root,
            )
        assert refusal.value.remedy == "cjdev build -p release"

    def test_a_branch_set_without_the_framework_names_the_fix(self, tmp_path: Path):
        # Act / Assert
        with pytest.raises(PreconditionError, match="cangjie_test_framework"):
            self.use_case().plan(
                tmp_path, "main", profile=Profile.DEBUG, paths=[tmp_path], cwd=tmp_path
            )

    def test_a_path_that_does_not_exist_is_the_invocation_being_wrong(self, root: Path):
        # Act / Assert
        with pytest.raises(UsageError, match="no such test path"):
            self.use_case().plan(
                root,
                "main",
                profile=Profile.DEBUG,
                paths=[root / "main/cangjie_test/testsuites/LLT/nope"],
                cwd=root,
            )

    def test_naming_nothing_is_refused_rather_than_running_the_whole_suite(
        self, root: Path
    ):
        # Act / Assert
        with pytest.raises(UsageError, match="name what to test"):
            self.use_case().plan(
                root, "main", profile=Profile.DEBUG, paths=[], cwd=root
            )

    def test_a_relative_path_is_resolved_before_it_is_classified(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        monkeypatch.chdir(root / "main/cangjie_test/testsuites")

        # Act
        plan = self.use_case().plan(
            root, "main", profile=Profile.DEBUG, paths=[Path("LLT/x")], cwd=root
        )

        # Assert
        assert (
            str(root / "main/cangjie_test/testsuites/LLT/x")
            in plan.runs[0].command.argv
        )


class TestApply:
    def test_the_results_file_is_read_into_the_summary(self):
        # Arrange
        executor = FakeExecutor()
        use_case = RunTests(
            executor=executor,
            file_system=FakeFileSystem(),
            host=lambda: HOST,
            read_results=lambda _: RESULTS,
        )

        # Act
        report = use_case.apply(plan_for({Suite.LLT: (LLT,)}))

        # Assert
        result = report.suites[0].result
        assert result is not None
        assert result.failed == 3
        assert not report.ok

    def test_a_run_that_wrote_no_results_is_not_a_success(self):
        # Arrange
        use_case = RunTests(
            executor=FakeExecutor(exit_code=1),
            file_system=FakeFileSystem(),
            host=lambda: HOST,
            read_results=lambda _: None,
        )

        # Act
        report = use_case.apply(plan_for({Suite.LLT: (LLT,)}))

        # Assert
        assert report.suites[0].exit_code == 1
        assert report.suites[0].result is None
        assert not report.ok

    def test_a_clean_run_is_ok(self):
        # Arrange
        clean = '[{"name": "x", "total": 1, "PASS": 1, "FAIL": 0, "tests": []}]'
        use_case = RunTests(
            executor=FakeExecutor(),
            file_system=FakeFileSystem(),
            host=lambda: HOST,
            read_results=lambda _: clean,
        )

        # Act
        report = use_case.apply(plan_for({Suite.LLT: (LLT,)}))

        # Assert
        assert report.ok

    def test_a_previous_run_s_results_go_before_this_one_starts(self, tmp_path: Path):
        # Arrange
        fs = FakeFileSystem()
        plan = decide(
            WorkspaceLayout(tmp_path),
            "main",
            Profile.DEBUG,
            HOST,
            {Suite.LLT: (tmp_path,)},
            cwd=tmp_path,
        )
        stale = Path(plan.runs[0].results)
        stale.parent.mkdir(parents=True)
        stale.write_text("[]")
        use_case = RunTests(
            executor=FakeExecutor(),
            file_system=fs,
            host=lambda: HOST,
            read_results=lambda _: None,
        )

        # Act
        use_case.apply(plan)

        # Assert: a run that dies before writing must not be reported with
        # the last run's results.
        assert fs.removed == [plan.runs[0].results]
