from pathlib import Path

import pytest

from cjdev.application.ports import Command, Completed
from cjdev.errors import CommandError
from cjdev.infra.executor import build_executor
from cjdev.infra.executor.host import HostExecutor


def echo(text: str, *, mutates: bool = True) -> Command:
    return Command(argv=("echo", text), cwd=Path.cwd(), mutates=mutates)


def failing(*, mutates: bool = True) -> Command:
    return Command(
        argv=("sh", "-c", "echo boom >&2; exit 3"), cwd=Path.cwd(), mutates=mutates
    )


class TestHostExecutor:
    def test_captures_output_rather_than_streaming_it(self):
        # Output already printed cannot be reordered into manifest order
        # later, so the executor must hold it.
        result = HostExecutor().run(echo("hello"))

        assert result.ok
        assert result.stdout.strip() == "hello"

    def test_a_non_zero_exit_raises_with_the_command_and_its_output(self):
        with pytest.raises(CommandError) as caught:
            HostExecutor().run(failing())

        message = str(caught.value)
        assert "exited 3" in message
        assert "boom" in message  # the tail of the output, not a traceback

    def test_check_false_reports_the_failure_instead_of_raising(self):
        result = HostExecutor().run(failing(), check=False)

        assert not result.ok
        assert result.exit_code == 3


class TestDryRun:
    def test_a_mutating_command_is_printed_and_not_run(self):
        printed: list[str] = []
        executor = build_executor(dry_run=True, emit=printed.append)

        result = executor.run(
            Command(argv=("rm", "-rf", "/"), cwd=Path.cwd(), mutates=True)
        )

        assert result == Completed(result.command, 0, "", "")
        assert printed == ["rm -rf /  # ."]

    def test_a_read_only_command_still_runs(self):
        # A dry run that could not inspect the world would print a plan built
        # on guesses rather than the plan that would actually execute.
        printed: list[str] = []
        executor = build_executor(dry_run=True, emit=printed.append)

        result = executor.run(echo("observed", mutates=False))

        assert result.stdout.strip() == "observed"
        assert printed == []


class TestVerbose:
    def test_every_invocation_is_echoed(self):
        printed: list[str] = []
        executor = build_executor(verbose=True, emit=printed.append)

        executor.run(echo("hi"))

        assert printed == ["$ echo hi  # ."]

    def test_a_failure_is_echoed_before_it_propagates(self):
        printed: list[str] = []
        executor = build_executor(verbose=True, emit=printed.append)

        with pytest.raises(CommandError):
            executor.run(failing())

        assert printed[-1] == "  exited 3"

    def test_quiet_by_default(self):
        printed: list[str] = []

        build_executor(emit=printed.append).run(echo("hi"))

        assert printed == []
