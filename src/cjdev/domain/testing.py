"""The test framework's vocabulary: suites, the files each host runs them with,
and what a run's results say.

`cangjie_test` holds two suites, LLT and HLT, and each wants its own test
list and config per host. Nothing upstream says which pairs go together; the
table below is read off the file names in `cangjie_test/testsuites`, and a
caller who knows better overrides it after `--`, where the framework's
argparse lets the last `--test_list` and `--test_cfg` win.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import PurePath, PurePosixPath
from typing import Any, final

from cjdev.errors import CjdevError, PreconditionError

TESTSUITES = PurePosixPath("testsuites")
"""Where the suites sit inside the `cangjie_test` worktree."""

DEFAULT_ARGS = ("-pFAIL", "--fail-verbose")
"""Only what failed, with its commands and output: a passing case's line is
noise in a run of thousands."""

FAIL = "FAIL"
PASS = "PASS"
NOT_RUN = "NOT_RUN"

_MISSING_TOOL = re.compile(r"([^\s:]+): command not found")


@final
@unique
class Suite(Enum):
    LLT = "LLT"
    HLT = "HLT"

    def __str__(self) -> str:
        return self.value


@final
@dataclass(frozen=True)
class SuiteFiles:
    """Relative to the suite's own directory."""

    lists: tuple[PurePosixPath, ...]
    """Concatenated by the framework in this order, so an exclude file without
    a section header lands in the test list's `[EXCLUDE-TEST-CASE]`."""
    cfg: PurePosixPath


_LLT = PurePosixPath("configs/cjnative")

LLT_FILES: Mapping[str, SuiteFiles] = {
    "linux_x86_64": SuiteFiles(
        lists=(PurePosixPath("cjnative_testlist"),),
        cfg=_LLT / "cjnative_test.cfg",
    ),
    "linux_aarch64": SuiteFiles(
        lists=(
            PurePosixPath("cjnative_testlist"),
            _LLT / "exclude_cjnative_aarch64",
        ),
        cfg=_LLT / "cjnative_test_linux_aarch64.cfg",
    ),
    "darwin_x86_64": SuiteFiles(
        lists=(PurePosixPath("cjnative_testlist"), _LLT / "exclude_cjnative_darwin"),
        cfg=_LLT / "cjnative_test_darwin.cfg",
    ),
    "darwin_aarch64": SuiteFiles(
        lists=(
            PurePosixPath("cjnative_testlist"),
            _LLT / "exclude_cjnative_darwin",
            _LLT / "exclude_cjnative_darwin_aarch64",
        ),
        cfg=_LLT / "cjnative_test_darwin_aarch64.cfg",
    ),
}

HLT_HOSTS: Mapping[str, str] = {
    "linux_x86_64": "linux_x64",
    "linux_aarch64": "linux_aarch64",
    "darwin_x86_64": "mac_x64",
    "darwin_aarch64": "mac_aarch64",
}
"""HLT names its config directories `<host>-<target>` in a spelling of its
own; a native run is the pair with itself."""


def suite_files(suite: Suite, target: str) -> SuiteFiles:
    if suite is Suite.LLT:
        files = LLT_FILES.get(target)
    else:
        host = HLT_HOSTS.get(target)
        configs = PurePosixPath("configs/cjnative")
        files = (
            None
            if host is None
            else SuiteFiles(
                lists=(
                    PurePosixPath("testlist"),
                    configs / "exclude_common",
                    configs / f"{host}-{host}" / "exclude_common",
                ),
                cfg=configs / f"{host}-{host}" / "basic.cfg",
            )
        )
    if files is None:
        raise PreconditionError(
            f"cjdev knows no {suite} test list and config for {target}.",
            remedy="pass --test_list and --test_cfg after `--`",
        )
    return files


@final
@dataclass(frozen=True)
class Failure:
    case: str
    log: PurePath | None
    missing: tuple[str, ...]
    """The tools a command could not find. A case that failed for this reason
    says nothing about the code under test."""


@final
@dataclass(frozen=True)
class SuiteResult:
    suite: Suite
    counts: Mapping[str, int]
    """Per framework status, `PASS`, `FAIL` and the rest, summed over every
    path the run was given."""
    failures: tuple[Failure, ...]

    @property
    def passed(self) -> int:
        return self.counts.get(PASS, 0)

    @property
    def failed(self) -> int:
        return self.counts.get(FAIL, 0)

    def missing_tools(self) -> dict[tuple[str, ...], tuple[Failure, ...]]:
        grouped: dict[tuple[str, ...], list[Failure]] = {}
        for failure in self.failures:
            if failure.missing:
                grouped.setdefault(failure.missing, []).append(failure)
        return {tools: tuple(cases) for tools, cases in sorted(grouped.items())}

    def other_failures(self) -> tuple[Failure, ...]:
        return tuple(failure for failure in self.failures if not failure.missing)


def parse_results(
    suite: Suite, text: str, *, source: str, log_dir: PurePath
) -> SuiteResult:
    """What `--json_output` wrote: one entry per test path, each with its
    status counts and, under `-pFAIL`, the failed cases with their output.

    Read from the file rather than from the console, because the console is
    the framework's progress display and its summary line is a format nobody
    promised to keep.

    `log_file` there is a name, not a path: the file is that name plus `.log`
    in the run's `--log_dir`.
    """
    try:
        document: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CjdevError(f"{source} is not the framework's JSON: {exc}") from exc
    if not isinstance(document, list):
        raise CjdevError(f"{source} is not the framework's JSON: not a list.")
    counts: dict[str, int] = {}
    failures: list[Failure] = []
    for entry in document:
        for key, value in entry.items():
            if key not in ("name", "total", "tests") and isinstance(value, int):
                counts[key] = counts.get(key, 0) + value
        failures.extend(
            Failure(
                case=str(test.get("name", "")),
                log=log_dir / f"{test['log_file']}.log"
                if test.get("log_file")
                else None,
                missing=missing_tools(test.get("output")),
            )
            for test in entry.get("tests", ())
            if test.get("result") == FAIL
        )
    return SuiteResult(suite=suite, counts=counts, failures=tuple(failures))


def missing_tools(output: object) -> tuple[str, ...]:
    """The programs bash reported missing, in a case's command output.

    `output` is a list of per-command results, or one string when the case
    failed before any command ran.
    """
    if isinstance(output, str):
        texts = [output]
    elif isinstance(output, list):
        texts = [
            str(result.get(stream) or "")
            for result in output
            if isinstance(result, dict)
            for stream in ("stdout", "stderr")
        ]
    else:
        texts = []
    found = {match for text in texts for match in _MISSING_TOOL.findall(text)}
    return tuple(sorted(found))
