from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast

from typer.main import get_command
from typer.testing import CliRunner

from cjdev.bootstrap import Container
from cjdev.cli import cli, cli_cb
from cjdev.cli._context import CjdevContext
from cjdev.cli.build import complete_unit
from cjdev.errors import ManifestError, NotImplementedYetError

runner = CliRunner()


def _walk(command: object) -> Iterator[object]:
    yield command
    for subcommand in getattr(command, "commands", {}).values():
        yield from _walk(subcommand)


def test_help_lists_commands():
    result = runner.invoke(cli, ["-h"])

    assert result.exit_code == 0
    for command in ("init", "status", "clean", "build"):
        assert command in result.output


class TestBuildTakesItsUnitsFromTheManifest:
    """One command over manifest data, not one hand-written stub per unit.

    Thirteen stubs and four manifest entries could not disagree with each
    other by accident, which is exactly what they were doing (R11).
    """

    def test_an_unknown_unit_is_refused_with_the_known_ones(self):
        # The exit code comes from `main()`, which CliRunner does not go
        # through, so the type is what carries "preconditions unmet" here.
        result = runner.invoke(cli, ["build", "nope"])

        assert isinstance(result.exception, ManifestError)
        assert ManifestError.exit_code == 3  # UX-5
        assert "compiler, runtime, stdlib, cjpm" in str(result.exception)

    def test_naming_a_unit_pulls_in_what_it_needs(self):
        # `cjdev build stdlib` is `--upto stdlib` (BUILD-2).
        result = runner.invoke(cli, ["build", "stdlib"])

        assert "compiler, runtime, stdlib" in str(result.exception)

    def test_no_arguments_means_the_whole_sdk(self):
        result = runner.invoke(cli, ["build"])

        assert "compiler, runtime, stdlib, cjpm" in str(result.exception)

    def test_completion_offers_manifest_units(self):
        assert complete_unit("cj") == ["cjpm"]
        assert "stdlib" in complete_unit("")


def test_every_command_uses_the_typed_context():
    # Guards against a missing `cls=`: the annotation would still type-check
    # while the command silently received a bare click Context at run time.
    for command in _walk(get_command(cli)):
        assert getattr(command, "context_class", None) is CjdevContext, command


def test_the_root_callback_puts_a_container_on_the_context():
    # Called directly rather than through a subcommand: every real command
    # currently raises, which would mask whether the wiring ran at all.
    ctx = SimpleNamespace(obj=None)

    cli_cb(cast(CjdevContext, ctx))

    assert isinstance(ctx.obj, Container)


def test_the_container_loads_the_bundled_manifest():
    assert Container().manifest.projects


def test_unimplemented_commands_say_so_rather_than_pretending():
    # Until M1 lands these are wired but empty. Silently exiting 0 would be
    # worse than failing: it reads as "the workspace is fine".
    result = runner.invoke(cli, ["status"])

    assert isinstance(result.exception, NotImplementedYetError)
    assert "M1" in str(result.exception)
