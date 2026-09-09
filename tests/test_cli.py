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
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import (
    InputRequiredError,
    PreconditionError,
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
    for command in ("init", "status"):
        assert command in result.output


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
    # hangs with nothing on either stream.
    assert isinstance(_prompt_with_stdin(isatty=False), NonInteractivePrompt)
    assert isinstance(_prompt_with_stdin(isatty=True), InteractivePrompt)


def test_consent_given_up_front_does_not_also_answer_a_wizard():
    # Consent is permission, not a setting. The two must not collapse into
    # one knob here, or whatever eventually supplies the permission would
    # silently pick the settings as well.
    assert isinstance(
        _prompt_with_stdin(isatty=True, assume_yes=True), InteractivePrompt
    )
    assert isinstance(
        _prompt_with_stdin(isatty=True, assume_yes=True, interactive=False),
        NonInteractivePrompt,
    )


def _prompt_with_stdin(
    *, isatty: bool, assume_yes: bool = False, interactive: bool = True
) -> object:
    with mock.patch.object(
        bootstrap.sys, "stdin", SimpleNamespace(isatty=lambda: isatty)
    ):
        return Container().prompt(interactive=interactive, assume_yes=assume_yes)


class TestInitNeedsSomewhereToAsk:
    def test_no_terminal_is_a_refusal_rather_than_a_default_set(self, tmp_path: Path):
        # The wizard is the only way `init` learns the project set, and there
        # is no flag that supplies one yet. Picking a set unasked would fetch
        # gigabytes nobody chose.
        result = runner.invoke(cli, ["init", str(tmp_path / "ws")])

        assert isinstance(result.exception, InputRequiredError)
        assert InputRequiredError.exit_code == 3  # preconditions unmet
        assert not (tmp_path / "ws").exists()

    def test_a_dry_run_still_works_without_one(self, tmp_path: Path):
        # It asks nothing, so the plan is available to a pipe.
        result = runner.invoke(cli, ["init", str(tmp_path / "ws"), "--dry-run"])

        assert result.exit_code == 0


class TestWorkspacesMayNest:
    def test_a_root_inside_a_workspace_is_allowed(self, empty_workspace: Path):
        # `find_root` answers with the nearest marker, so an inner workspace
        # shadows the outer one and nothing has to be refused for it.
        result = runner.invoke(
            cli, ["init", str(empty_workspace / "inner"), "--dry-run"]
        )

        assert result.exit_code == 0

    def test_re_running_on_the_workspace_itself_is_supported(
        self, empty_workspace: Path
    ):
        result = runner.invoke(cli, ["init", str(empty_workspace), "--dry-run"])

        assert result.exit_code == 0


class TestInitDoesNotOverclaim:
    def test_a_dry_run_does_not_say_the_workspace_is_ready(self, tmp_path: Path):
        # It creates nothing, so "ready" would be a claim about a workspace
        # that does not exist - the one message a dry run must never print.
        result = runner.invoke(cli, ["init", str(tmp_path / "ws"), "--dry-run"])

        assert result.exit_code == 0
        assert "Workspace ready" not in result.output
        assert "was not touched" in result.output
        assert not (tmp_path / "ws").exists()

    def test_a_dry_run_prints_the_skeleton_it_would_create(self, tmp_path: Path):
        # Printed by the dry-run filesystem itself rather than by a second
        # renderer that would have to be kept in step with it.
        result = runner.invoke(cli, ["init", str(tmp_path / "ws"), "--dry-run"])

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
        self, empty_workspace: Path
    ):
        # A parser owes nothing to whatever else the command had to say, so
        # the whole of stdout has to parse while -v is still echoing.
        store = Path(WorkspaceLayout(empty_workspace).object_store("cangjie_compiler"))
        store.mkdir(parents=True)

        result = runner.invoke(cli, ["status", str(empty_workspace), "--json", "-v"])

        assert json.loads(result.stdout)["command"] == "status"
        assert "$ git" in result.stderr

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

    def test_a_failure_travels_inside_the_document_rather_than_beside_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        # Through `main()` rather than the runner: the envelope for a failure
        # is printed on the way out, which is the path CliRunner skips.
        monkeypatch.setattr(sys, "argv", ["cjdev", "status", str(tmp_path), "--json"])

        with pytest.raises(SystemExit) as stopped:
            main()

        document = json.loads(capsys.readouterr().out)
        assert stopped.value.code == 3  # preconditions unmet
        assert not document["ok"]
        assert document["command"] == "status"
        failure = document["errors"][0]
        assert failure["code"] == "precondition"
        # Null rather than invented: a caller that cannot tell a good guess
        # from a bad one is better served by nothing.
        assert failure["remedy"] is None

    def test_the_same_failure_reads_as_a_line_when_nobody_asked_for_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        # The code and the message are the same either way; only the shape
        # differs, and stdout stays empty for a run that produced no document.
        monkeypatch.setattr(sys, "argv", ["cjdev", "status", str(tmp_path)])

        with pytest.raises(SystemExit):
            main()

        printed = capsys.readouterr()
        assert printed.out == ""
        assert "error: " in printed.err

    def test_a_named_remedy_is_printed_with_the_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        # The remedy is a field rather than a sentence in the message: the
        # caller it exists for re-runs the command, and this is where it
        # learns what to add. `init` without a terminal is the one failure
        # that has a fix worth naming.
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: False))
        monkeypatch.setattr(sys, "argv", ["cjdev", "init", str(tmp_path / "ws")])

        with pytest.raises(SystemExit):
            main()

        assert "try: run it from a terminal" in capsys.readouterr().err
