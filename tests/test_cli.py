from collections.abc import Iterator

from typer.main import get_command
from typer.testing import CliRunner

from cjdev.cli import cli
from cjdev.cli.context import CjdevContext

runner = CliRunner()


def _walk(command: object) -> Iterator[object]:
    yield command
    for subcommand in getattr(command, "commands", {}).values():
        yield from _walk(subcommand)


def test_help_lists_commands():
    result = runner.invoke(cli, ["-h"])

    assert result.exit_code == 0
    assert "init" in result.output
    assert "status" in result.output


def test_every_command_uses_the_typed_context():
    # Guards against a missing `cls=`: the annotation would still type-check
    # while the command silently received a bare click Context at run time.
    for command in _walk(get_command(cli)):
        assert getattr(command, "context_class", None) is CjdevContext, command


def test_status_reaches_the_container_through_the_context():
    result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0, result.output
