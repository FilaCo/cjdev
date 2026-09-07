import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from cjdev.bootstrap import Container
from cjdev.cli import cli, cli_cb
from cjdev.cli._context import CjdevContext
from cjdev.cli.build import complete_unit
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import ManifestError, NotImplementedYetError, PreconditionError

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
    other by accident, which is exactly what they were doing.
    """

    def test_an_unknown_unit_is_refused_with_the_known_ones(self):
        # The exit code comes from `main()`, which CliRunner does not go
        # through, so the type is what carries "preconditions unmet" here.
        result = runner.invoke(cli, ["build", "nope"])

        assert isinstance(result.exception, ManifestError)
        assert ManifestError.exit_code == 3  # preconditions unmet
        assert "compiler, runtime, stdlib, cjpm" in str(result.exception)

    def test_naming_a_unit_pulls_in_what_it_needs(self):
        # `cjdev build stdlib` is `--upto stdlib`.
        result = runner.invoke(cli, ["build", "stdlib"])

        assert "compiler, runtime, stdlib" in str(result.exception)

    def test_no_arguments_means_the_whole_sdk(self):
        result = runner.invoke(cli, ["build"])

        assert "compiler, runtime, stdlib, cjpm" in str(result.exception)

    def test_completion_offers_manifest_units(self):
        assert complete_unit("cj") == ["cjpm"]
        assert "stdlib" in complete_unit("")


class TestStatus:
    @pytest.fixture
    def empty_workspace(self, tmp_path: Path) -> Path:
        # A marker and nothing else: `init` creates `bare/` only once it has a
        # project to put in it, and status must survive that state.
        Path(WorkspaceLayout(tmp_path).marker).mkdir()
        return tmp_path

    def test_it_refuses_outside_a_workspace(self, tmp_path: Path):
        result = runner.invoke(cli, ["status", str(tmp_path)])

        assert isinstance(result.exception, PreconditionError)
        assert PreconditionError.exit_code == 3  # preconditions unmet

    def test_an_empty_workspace_reports_the_manifest_as_absent(
        self, empty_workspace: Path
    ):
        result = runner.invoke(cli, ["status", str(empty_workspace)])

        assert result.exit_code == 0
        assert "cangjie_compiler" in result.output
        assert "No branch sets yet" in result.output

    def test_an_unreadable_store_is_reported_and_is_not_a_success(
        self, empty_workspace: Path
    ):
        # A report that saw only part of the workspace must not be mistaken
        # for a clean one by a prompt or a script.
        layout = WorkspaceLayout(empty_workspace)
        store = Path(layout.object_store("cangjie_compiler"))
        store.mkdir(parents=True)
        (store / "HEAD").write_text("not a git repository")

        result = runner.invoke(cli, ["status", str(empty_workspace)])

        assert result.exit_code == 1
        assert "cangjie_compiler" in result.output
        assert "not a git repository" in result.output

    def test_json_is_parseable_rather_than_pretty(self, empty_workspace: Path):
        # The whole point of --json is that something else reads it, so rich
        # must not colour, rewrap or reinterpret it on the way out.
        result = runner.invoke(cli, ["status", str(empty_workspace), "--json"])

        report = json.loads(result.output)
        assert report["branch_sets"] == []
        assert {p["name"] for p in report["projects"]} == {
            p.name for p in Container().manifest.projects
        }
        assert not any(p["provisioned"] for p in report["projects"])


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
    # `build` is wired to the manifest but has no builder behind it until M2.
    # Silently exiting 0 would be worse than failing: it reads as "it built".
    result = runner.invoke(cli, ["build"])

    assert isinstance(result.exception, NotImplementedYetError)
    assert "M2" in str(result.exception)


class TestInitDoesNotOverclaim:
    def test_a_dry_run_does_not_say_the_workspace_is_ready(self, tmp_path: Path):
        # It creates nothing, so "ready" would be a claim about a workspace
        # that does not exist - the one message a dry run must never print.
        result = runner.invoke(
            cli, ["init", str(tmp_path / "ws"), "--defaults", "--dry-run"]
        )

        assert result.exit_code == 0
        assert "Workspace ready" not in result.output
        assert "was not touched" in result.output
        assert not (tmp_path / "ws").exists()

    def test_a_dry_run_prints_the_skeleton_it_would_create(self, tmp_path: Path):
        # Printed by the dry-run filesystem itself rather than by a second
        # renderer that would have to be kept in step with it.
        result = runner.invoke(
            cli, ["init", str(tmp_path / "ws"), "--defaults", "--dry-run"]
        )

        assert "mkdir -p" in result.output
        assert ".cjdev" in result.output


def test_a_reported_error_is_prefixed_rather_than_traced(capsys):
    from cjdev.cli._console import print_error

    print_error("something went wrong\n  and here is why")

    printed = capsys.readouterr().err
    assert printed.startswith("error: something went wrong")
    assert "and here is why" in printed
