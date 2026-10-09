"""`cjdev test`: the test framework, against the branch set's own dist.

By hand this is a `main.py` invocation with four paths and three variables to
get right, and the two ways it went wrong were both the dist: tests run
against a profile that was never fully built, and `CANGJIE_HOME` pointing at
the other profile's SDK. So the environment is a build step's, the profile is
the branch set's, and a dist that is not there is a refusal rather than a
thousand failures.

One framework run per suite, because the test list and config are per suite;
the paths of one suite share a run, which is how the framework takes them.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import final

from cjdev.application.build_units import HostProvider, build_environment
from cjdev.application.ports import Command, Executor, FileSystem
from cjdev.domain.build import Host, Profile
from cjdev.domain.environment import DEFAULT_ENVIRONMENT, Environment
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.testing import (
    DEFAULT_ARGS,
    TESTSUITES,
    Suite,
    SuiteResult,
    parse_results,
    suite_files,
)
from cjdev.errors import PreconditionError, UsageError

FRAMEWORK = "cangjie_test_framework"
TESTS = "cangjie_test"

ReadResults = Callable[[PurePath], str | None]
"""The results file's text, or None when there is none. Injected, because a
dry run ran nothing and must not report a previous run's file as its own."""


@final
@dataclass(frozen=True)
class SuiteRun:
    suite: Suite
    command: Command
    log_dir: PurePath
    results: PurePath


@final
@dataclass(frozen=True)
class TestPlan:
    root: PurePath
    branch_set: str
    profile: Profile
    dist: PurePath
    runs: tuple[SuiteRun, ...]


@final
@dataclass(frozen=True)
class SuiteOutcome:
    suite: Suite
    exit_code: int
    results: PurePath
    result: SuiteResult | None
    """None when the framework wrote no results: it died before the end, or
    this was a dry run."""


@final
@dataclass(frozen=True)
class TestReport:
    plan: TestPlan
    suites: tuple[SuiteOutcome, ...]

    @property
    def ok(self) -> bool:
        return all(
            outcome.exit_code == 0
            and outcome.result is not None
            and outcome.result.failed == 0
            for outcome in self.suites
        )


def classify(
    tests: PurePath, paths: Sequence[PurePath]
) -> dict[Suite, tuple[PurePath, ...]]:
    """Which suite each path belongs to, by where it sits in `cangjie_test`.

    In the order the caller named them, so a run reads the way it was asked.
    """
    grouped: dict[Suite, list[PurePath]] = {}
    for path in paths:
        suite = next(
            (
                suite
                for suite in Suite
                if path.is_relative_to(tests / TESTSUITES / suite.value)
            ),
            None,
        )
        if suite is None:
            raise UsageError(
                f"{path} is not inside {tests / TESTSUITES}/LLT or /HLT, so no "
                f"suite says how to run it."
            )
        grouped.setdefault(suite, []).append(path)
    return {suite: tuple(found) for suite, found in grouped.items()}


def decide(
    layout: WorkspaceLayout,
    branch_set: str,
    profile: Profile,
    host: Host,
    suites: dict[Suite, tuple[PurePath, ...]],
    *,
    cwd: PurePath,
    environment: Environment = DEFAULT_ENVIRONMENT,
    passthrough: Sequence[str] = (),
) -> TestPlan:
    where = environment.mode.value
    framework = layout.worktree(branch_set, FRAMEWORK)
    tests = layout.worktree(branch_set, TESTS)
    env = build_environment(layout, branch_set, where, profile, host) | {
        # HLT's configs read the suite root from it, and upstream leaves it
        # to the caller's shell.
        "CANGJIE_TEST": str(tests),
    }
    runs = []
    for suite, paths in suites.items():
        files = suite_files(suite, host.target)
        base = tests / TESTSUITES / suite.value
        scratch = layout.test_dir(branch_set, where, profile.value, suite.value)
        results = scratch / "results.json"
        runs.append(
            SuiteRun(
                suite=suite,
                command=Command(
                    argv=(
                        "python3",
                        str(framework / "main.py"),
                        "--test_cfg",
                        str(base / files.cfg),
                        "--test_list",
                        ",".join(str(base / listed) for listed in files.lists),
                        # Without these the framework writes into its own
                        # worktree, under `test_temp`, which is shared by
                        # every profile and every run.
                        "--temp_dir",
                        str(scratch / "run"),
                        "--log_dir",
                        str(scratch / "log"),
                        "--json_output",
                        str(results),
                        # Its default is one case at a time.
                        "-j",
                        str(host.jobs),
                        *DEFAULT_ARGS,
                        *(str(path) for path in paths),
                        # Last, so a repeated option the caller passes is the
                        # one argparse keeps.
                        *passthrough,
                    ),
                    cwd=Path(cwd),
                    env=env,
                    interactive=True,
                    what=f"testing {suite}",
                ),
                log_dir=scratch / "log",
                results=results,
            )
        )
    return TestPlan(
        root=layout.root,
        branch_set=branch_set,
        profile=profile,
        dist=layout.dist_dir(branch_set, where, profile.value),
        runs=tuple(runs),
    )


@final
class RunTests:
    def __init__(
        self,
        executor: Executor,
        file_system: FileSystem,
        host: HostProvider,
        read_results: ReadResults,
        environment: Environment = DEFAULT_ENVIRONMENT,
    ) -> None:
        self._executor = executor
        self._fs = file_system
        self._host = host
        self._read_results = read_results
        self._environment = environment

    def plan(
        self,
        root: Path,
        branch_set: str,
        *,
        profile: Profile,
        paths: Sequence[Path],
        cwd: Path,
        passthrough: Sequence[str] = (),
    ) -> TestPlan:
        layout = WorkspaceLayout(root)
        if not paths:
            raise UsageError("name what to test: a case or a directory of a suite.")
        for project in (FRAMEWORK, TESTS):
            if not Path(layout.worktree(branch_set, project)).is_dir():
                raise PreconditionError(
                    f"{project} has no worktree in branch set {branch_set}.",
                    remedy=f"cjdev branch new {branch_set}",
                )
        where = self._environment.mode.value
        dist = layout.dist_dir(branch_set, where, profile.value)
        if not Path(dist).is_dir():
            raise PreconditionError(
                f"branch set {branch_set} has no {profile} SDK to test.",
                remedy=f"cjdev build -p {profile}",
            )
        missing = [path for path in paths if not path.exists()]
        if missing:
            raise UsageError(f"no such test path: {', '.join(map(str, missing))}.")
        tests = layout.worktree(branch_set, TESTS)
        return decide(
            layout,
            branch_set,
            profile,
            self._host(),
            classify(tests, [path.resolve() for path in paths]),
            cwd=cwd,
            environment=self._environment,
            passthrough=passthrough,
        )

    def apply(self, plan: TestPlan) -> TestReport:
        outcomes = []
        for run in plan.runs:
            self._fs.mkdir(run.log_dir)
            # A run that dies before writing its results must not be
            # reported with the last run's.
            if Path(run.results).exists():
                self._fs.remove(run.results)
            # Not checked: the framework exits 0 with failures, and nonzero
            # only when something went wrong around them.
            completed = self._executor.run(run.command, check=False)
            text = self._read_results(run.results)
            outcomes.append(
                SuiteOutcome(
                    suite=run.suite,
                    exit_code=completed.exit_code,
                    results=run.results,
                    result=None
                    if text is None
                    else parse_results(
                        run.suite, text, source=str(run.results), log_dir=run.log_dir
                    ),
                )
            )
        return TestReport(plan=plan, suites=tuple(outcomes))
