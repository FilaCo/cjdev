"""The test framework's vocabulary: which files a suite runs with, and what a
run's results say.

`data/framework_results.json` is what the real `main.py` wrote for a toy LLT
suite of four cases - one passing, one plain failure and two that call a
`gnustep-config` the machine does not have - with its paths rewritten to /ws.
"""

from pathlib import Path, PurePath, PurePosixPath

import pytest

from cjdev.domain.testing import (
    Suite,
    missing_tools,
    parse_results,
    suite_files,
)
from cjdev.errors import CjdevError, PreconditionError

RESULTS = (Path(__file__).parent / "data" / "framework_results.json").read_text()
LOGS = PurePath("/ws/.cjdev/build/main/test/host/debug/LLT/log")


def parsed():
    return parse_results(Suite.LLT, RESULTS, source="results.json", log_dir=LOGS)


class TestSuiteFiles:
    def test_llt_on_linux_x86_is_the_list_and_config_upstream_ships_for_it(self):
        # Act
        files = suite_files(Suite.LLT, "linux_x86_64")

        # Assert
        assert files.lists == (PurePosixPath("cjnative_testlist"),)
        assert files.cfg == PurePosixPath("configs/cjnative/cjnative_test.cfg")

    def test_an_exclude_file_follows_the_list_it_excludes_from(self):
        # Act
        files = suite_files(Suite.LLT, "linux_aarch64")

        # Assert: the framework concatenates the lists, so a headerless
        # exclude file only excludes when it lands after the list's own
        # [EXCLUDE-TEST-CASE].
        assert files.lists[0] == PurePosixPath("cjnative_testlist")
        assert files.lists[1].name == "exclude_cjnative_aarch64"

    def test_hlt_runs_the_native_pair_of_its_host(self):
        # Act
        files = suite_files(Suite.HLT, "linux_x86_64")

        # Assert
        assert files.cfg == PurePosixPath(
            "configs/cjnative/linux_x64-linux_x64/basic.cfg"
        )
        assert files.lists[0] == PurePosixPath("testlist")

    def test_an_unknown_host_is_refused_with_the_override_named(self):
        # Act / Assert
        with pytest.raises(PreconditionError) as refusal:
            suite_files(Suite.HLT, "windows_x86_64")
        assert refusal.value.remedy == "pass --test_list and --test_cfg after `--`"


class TestResults:
    def test_the_counts_are_the_framework_s(self):
        # Act
        result = parsed()

        # Assert
        assert (result.passed, result.failed) == (1, 3)

    def test_a_missing_tool_is_a_cause_of_its_own(self):
        # Act
        result = parsed()

        # Assert: two cases failing for want of gnustep-config say nothing
        # about the compiler, and must not be listed beside the one that does.
        groups = result.missing_tools()
        assert list(groups) == [("gnustep-config",)]
        assert [f.case for f in groups[("gnustep-config",)]] == [
            "compiler/objc/a.cj",
            "compiler/objc/b.cj",
        ]
        assert [f.case for f in result.other_failures()] == ["compiler/fail.cj"]

    def test_the_log_is_the_name_the_framework_gives_inside_its_log_dir(self):
        # Act
        failure = parsed().other_failures()[0]

        # Assert
        assert failure.log == LOGS / "fail_cj_d6f35adac3df11f1.log"

    def test_counts_are_summed_over_every_path_of_the_run(self):
        # Arrange: one entry per test path the run was given.
        text = '[{"name": "a", "total": 2, "PASS": 2, "FAIL": 0, "tests": []},' + (
            ' {"name": "b", "total": 1, "PASS": 0, "FAIL": 1, "tests": []}]'
        )

        # Act
        result = parse_results(Suite.HLT, text, source="r", log_dir=LOGS)

        # Assert
        assert (result.passed, result.failed) == (2, 1)

    def test_a_file_that_is_not_the_framework_s_json_is_a_failure_naming_it(self):
        # Act / Assert
        with pytest.raises(CjdevError, match=r"results\.json"):
            parse_results(Suite.LLT, "{", source="results.json", log_dir=LOGS)


class TestMissingTools:
    def test_a_case_that_failed_before_any_command_ran_has_one_string(self):
        # Act / Assert
        assert missing_tools("sh: cjfmt: command not found") == ("cjfmt",)

    def test_stdout_counts_too_because_a_pipe_carries_stderr_there(self):
        # Arrange: ERRCHECK is `cmd 2>&1 | compare`.
        output = [{"stdout": "bash: line 1: ObjCInteropGen: command not found"}]

        # Act / Assert
        assert missing_tools(output) == ("ObjCInteropGen",)

    def test_an_ordinary_failure_names_no_tool(self):
        # Act / Assert
        assert missing_tools([{"stdout": "", "stderr": "error: x"}]) == ()
