import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest import mock

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from cjdev import bootstrap, main
from cjdev.bootstrap import Container
from cjdev.cli import cli, cli_cb
from cjdev.cli._context import CjdevContext
from cjdev.cli._output import SCHEMA
from cjdev.cli.build import complete_unit
from cjdev.cli.init import complete_project
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import (
    InputRequiredError,
    ManifestError,
    NotImplementedYetError,
    PreconditionError,
    UsageError,
)
from cjdev.infra.prompt import InteractivePrompt, NonInteractivePrompt

runner = CliRunner()


@pytest.fixture
def empty_workspace(tmp_path: Path) -> Path:
    # A marker and nothing else: `init` creates `bare/` only once it has a
    # project to put in it, and status must survive that state.
    Path(WorkspaceLayout(tmp_path).marker).mkdir()
    return tmp_path


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


def test_no_terminal_means_no_question_rather_than_a_wait_for_one():
    # The one line standing between an unattended caller and a command that
    # hangs with nothing on either stream (UX-14).
    assert isinstance(
        _prompt_with_stdin(isatty=False, assume_yes=False), NonInteractivePrompt
    )
    assert isinstance(
        _prompt_with_stdin(isatty=True, assume_yes=False), InteractivePrompt
    )
    # `--yes` is an answer already given, so there is nothing left to ask even
    # with a terminal to ask at.
    assert isinstance(
        _prompt_with_stdin(isatty=True, assume_yes=True), NonInteractivePrompt
    )


def _prompt_with_stdin(*, isatty: bool, assume_yes: bool) -> object:
    with mock.patch.object(
        bootstrap.sys, "stdin", SimpleNamespace(isatty=lambda: isatty)
    ):
        return Container().prompt(assume_yes=assume_yes)


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


class TestTheEnvelope:
    """`--json` is a contract with something that is not a person.

    So the tests are about the shape of it - versioned, one document, on
    stdout, with failures inside rather than beside it - and not about which
    fields one command happens to report today.
    """

    def test_a_report_arrives_versioned_and_wrapped(self, empty_workspace: Path):
        result = runner.invoke(cli, ["status", str(empty_workspace), "--json"])

        document = json.loads(result.stdout)
        assert document["schema"] == SCHEMA
        assert document["command"] == "status"
        assert document["ok"]
        assert document["errors"] == []
        assert document["data"]["branch_sets"] == []
        assert {p["name"] for p in document["data"]["projects"]} == {
            p.name for p in Container().manifest.projects
        }

    def test_stdout_carries_the_document_and_the_transcript_goes_to_stderr(
        self, tmp_path: Path
    ):
        # The dry run still owes its command list (UX-1), and a parser still
        # owes nothing to whatever else the command had to say.
        result = runner.invoke(
            cli, ["init", str(tmp_path / "ws"), "--dry-run", "--json"]
        )

        document = json.loads(result.stdout)
        assert document["data"]["dry_run"]
        assert "mkdir -p" not in result.stdout
        assert "mkdir -p" in result.stderr

    def test_a_partly_read_workspace_is_a_document_and_a_failure_at_once(
        self, empty_workspace: Path
    ):
        # Everything that could be read is still worth reporting; `ok: false`
        # and the exit code are what stop it being mistaken for a clean run.
        store = Path(WorkspaceLayout(empty_workspace).object_store("cangjie_compiler"))
        store.mkdir(parents=True)
        (store / "HEAD").write_text("not a git repository")

        result = runner.invoke(cli, ["status", str(empty_workspace), "--json"])

        document = json.loads(result.stdout)
        assert result.exit_code == 1
        assert not document["ok"]
        assert document["data"]["projects"]
        failure = document["errors"][0]
        assert failure["code"] == "project_unreadable"
        assert failure["subject"] == "cangjie_compiler"

    def test_a_dry_run_reports_what_it_would_have_removed(self, empty_workspace: Path):
        # The one command whose plan is the whole of its result: what `clean`
        # would delete has to be readable without running it.
        result = runner.invoke(
            cli, ["clean", str(empty_workspace), "--dry-run", "--json"]
        )

        document = json.loads(result.stdout)
        assert document["command"] == "clean"
        assert document["ok"]
        assert document["data"]["dry_run"]
        assert (
            str(WorkspaceLayout(empty_workspace).marker) in document["data"]["removed"]
        )
        assert empty_workspace.is_dir()

    def test_a_failure_names_the_flag_that_would_have_answered_it(
        self, empty_workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        # Through `main()` rather than the runner: the envelope for a failure
        # is printed on the way out, which is the path CliRunner skips.
        monkeypatch.setattr(
            sys, "argv", ["cjdev", "clean", str(empty_workspace), "--json"]
        )

        with pytest.raises(SystemExit) as stopped:
            main()

        document = json.loads(capsys.readouterr().out)
        assert stopped.value.code == 3  # preconditions unmet
        assert not document["ok"]
        assert document["command"] == "clean"
        failure = document["errors"][0]
        assert failure["code"] == "input_required"
        assert failure["remedy"] == "re-run with --yes"

    def test_the_same_failure_reads_as_a_line_when_nobody_asked_for_json(
        self, empty_workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        # The code, the subject and the remedy are the same three either way;
        # only the shape differs (UX-13).
        monkeypatch.setattr(sys, "argv", ["cjdev", "clean", str(empty_workspace)])

        with pytest.raises(SystemExit):
            main()

        printed = capsys.readouterr()
        assert printed.out == ""
        assert "error: " in printed.err
        assert "try: re-run with --yes" in printed.err


class TestTheProjectSetCanBeNamedRatherThanTicked:
    """The wizard's question, asked on the command line.

    Without this a caller with no terminal can only take the default set:
    `--defaults` skips the question, it does not answer it.
    """

    def test_named_projects_answer_the_question(self, tmp_path: Path):
        result = runner.invoke(
            cli,
            [
                "init",
                str(tmp_path / "ws"),
                "-p",
                "cangjie_compiler",
                "--dry-run",
                "--json",
            ],
        )

        document = json.loads(result.stdout)
        assert document["data"]["selected"] == ["cangjie_compiler"]
        assert [c["project"] for c in document["data"]["changes"]] == [
            "cangjie_compiler"
        ]

    def test_the_order_is_the_manifest_s_and_not_the_caller_s(self, tmp_path: Path):
        # Every ordering cjdev produces is manifest order; naming projects
        # backwards must not be a way to reorder a fan-out.
        result = runner.invoke(
            cli,
            [
                "init",
                str(tmp_path / "ws"),
                "-p",
                "cangjie_runtime",
                "-p",
                "cangjie_compiler",
                "--dry-run",
                "--json",
            ],
        )

        document = json.loads(result.stdout)
        assert document["data"]["selected"] == ["cangjie_compiler", "cangjie_runtime"]

    def test_an_unknown_project_is_a_usage_error_listing_the_known_ones(
        self, tmp_path: Path
    ):
        result = runner.invoke(
            cli, ["init", str(tmp_path / "ws"), "-p", "nope", "--dry-run"]
        )

        assert isinstance(result.exception, UsageError)
        assert UsageError.exit_code == 2  # the invocation itself is wrong
        assert "cangjie_compiler" in str(result.exception)

    def test_naming_the_set_is_not_consent_to_the_deletion_it_implies(
        self, empty_workspace: Path
    ):
        # `--json` supplies answers; only `--yes` supplies permission. A
        # dropped project still costs everything fetched into it.
        store = Path(WorkspaceLayout(empty_workspace).object_store("cangjie_compiler"))
        store.mkdir(parents=True)

        result = runner.invoke(
            cli, ["init", str(empty_workspace), "-p", "cangjie_runtime", "--json"]
        )

        assert isinstance(result.exception, InputRequiredError)
        assert result.exception.remedy == "re-run with --yes"

    def test_completion_offers_manifest_projects(self):
        assert complete_project("cangjie_com") == ["cangjie_compiler"]
        assert "cangjie_runtime" in complete_project("")
