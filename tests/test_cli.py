from typer.testing import CliRunner

from cjdev.commands import cli

runner = CliRunner()


def test_help_lists_status():
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "status" in result.stdout


def test_status_runs():
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
