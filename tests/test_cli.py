import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from cjdev import bootstrap, main
from cjdev.application.new_branch_set import Enrolment, NewBranchSet
from cjdev.application.ports import Executor
from cjdev.application.report_status import DEFAULT_QUERY_JOBS
from cjdev.bootstrap import Container
from cjdev.cli import cli, cli_cb
from cjdev.cli._context import CjdevContext
from cjdev.cli._output import SCHEMA
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Manifest, Project, ProjectRole
from cjdev.errors import (
    InputRequiredError,
    ManifestError,
    PreconditionError,
    UsageError,
)
from cjdev.infra.config import render_workspace_config
from cjdev.infra.executor.host import HostExecutor
from cjdev.infra.git import provision_object_store
from cjdev.infra.prompt import InteractivePrompt, NonInteractivePrompt
from conftest import make_upstream

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
    for command in ("branch", "init", "status", "config"):
        assert command in result.output


class TestConfigShow:
    """`cjdev config show`: the effective config, in both renderings."""

    def test_outside_any_workspace_the_bundled_manifest_is_shown_as_such(
        self, tmp_path: Path
    ):
        # FR-9: the same answer `init` will act on, with no workspace in play.
        result = runner.invoke(cli, ["config", "show", str(tmp_path)])

        assert result.exit_code == 0
        assert "cangjie_compiler" in result.output

    def test_the_json_payload_carries_the_layer_of_every_value(self, tmp_path: Path):
        # FR-8: the machine surface hides nothing - provenance is always in
        # the document, whatever the verbosity flag said.
        result = runner.invoke(cli, ["config", "show", str(tmp_path), "--json"])

        document = json.loads(result.stdout)
        assert document["command"] == "config show"
        assert document["ok"]
        assert document["data"]["schema_version"] == {
            "value": 1,
            "layer": "bundled",
        }
        upstream = next(
            p["upstream"]
            for p in document["data"]["projects"]
            if p["name"] == "cangjie_compiler"
        )
        assert upstream == {
            "value": "https://gitcode.com/Cangjie/cangjie_compiler.git",
            "layer": "bundled",
        }

    def test_a_workspace_override_changes_the_effective_config(
        self, empty_workspace: Path
    ):
        # FR-1/FR-2: the nearest workspace's file layers over the bundled
        # manifest, one field of one project at a time.
        config = Path(WorkspaceLayout(empty_workspace).config_file)
        config.write_text(
            "[projects.cangjie_compiler]\n"
            'upstream = "https://gitcode.com/FilaCo/cangjie_compiler.git"\n'
        )

        result = runner.invoke(cli, ["config", "show", str(empty_workspace), "--json"])

        document = json.loads(result.stdout)
        upstream = next(
            p["upstream"]
            for p in document["data"]["projects"]
            if p["name"] == "cangjie_compiler"
        )
        assert upstream["value"] == "https://gitcode.com/FilaCo/cangjie_compiler.git"
        assert upstream["layer"] == "workspace"

    def test_verbose_names_the_layer_of_every_value(self, empty_workspace: Path):
        # FR-8: -v changes what is shown. The layers are in the table now -
        # and in the JSON payload they were there regardless.
        config = Path(WorkspaceLayout(empty_workspace).config_file)
        config.write_text('[projects.cangjie_compiler]\nupstream = "https://x/a.git"\n')

        plain = runner.invoke(cli, ["config", "show", str(empty_workspace)])
        verbose = runner.invoke(cli, ["config", "show", str(empty_workspace), "-v"])

        assert plain.exit_code == verbose.exit_code == 0
        assert "workspace" not in plain.output
        assert "workspace" in verbose.output
        assert "bundled" in verbose.output

    def test_verbose_lines_the_layer_column_up_for_scanning(
        self, empty_workspace: Path
    ):
        # The layer column exists to be skimmed vertically - "which of these
        # did I override". It prints before the value, in a fixed-width slot,
        # so every layer lands on the same column whatever the value is.
        config = Path(WorkspaceLayout(empty_workspace).config_file)
        config.write_text('[projects.cangjie_compiler]\nupstream = "https://x/a.git"\n')

        verbose = runner.invoke(cli, ["config", "show", str(empty_workspace), "-v"])

        assert verbose.exit_code == 0
        columns: set[int] = set()
        for line in verbose.output.splitlines():
            for word in ("bundled", "workspace"):
                if word in line:
                    columns.add(line.index(word))
        assert len(columns) == 1

    def test_no_line_of_the_table_carries_trailing_whitespace(
        self, empty_workspace: Path
    ):
        # Labels are padded to the column width only where something follows
        # on the line; padding a section header anyway left trailing
        # whitespace on a dozen lines of every run.
        for argv in (
            ["config", "show", str(empty_workspace)],
            ["config", "show", str(empty_workspace), "-v"],
        ):
            result = runner.invoke(cli, argv)

            assert result.exit_code == 0
            assert not any(line != line.rstrip() for line in result.output.splitlines())

    def test_a_broken_workspace_config_fails_with_the_file_named(
        self, empty_workspace: Path
    ):
        # FR-6: with two files in play, the refusal says which one refused.
        config = Path(WorkspaceLayout(empty_workspace).config_file)
        config.write_text("schema_version = 99\n")

        result = runner.invoke(cli, ["config", "show", str(empty_workspace)])

        assert isinstance(result.exception, ManifestError)
        assert "config.toml" in str(result.exception)

    def test_the_comment_only_template_layers_to_an_unchanged_manifest(
        self, empty_workspace: Path
    ):
        # FR-4, end to end: the file `init` writes must be a no-op layer.
        config = Path(WorkspaceLayout(empty_workspace).config_file)
        config.write_text(render_workspace_config())

        result = runner.invoke(cli, ["config", "show", str(empty_workspace), "--json"])

        document = json.loads(result.stdout)
        assert document["data"]["schema_version"]["layer"] == "bundled"
        assert len(document["data"]["projects"]) == len(Container().manifest().projects)


def test_a_workspace_override_changes_what_status_reports(
    empty_workspace: Path,
):
    # FR-1: the layering is not a `config show` toy - every command resolves
    # its set through the same composition root, so an added project is
    # reported as held-or-absent by `status` too.
    config = Path(WorkspaceLayout(empty_workspace).config_file)
    config.write_text(
        "[projects.mirror]\n"
        'role = "test_data"\n'
        'upstream = "https://example.invalid/mirror.git"\n'
        'default_branch = "main"\n'
    )

    result = runner.invoke(cli, ["status", str(empty_workspace), "--json"])

    document = json.loads(result.stdout)
    names = {p["name"] for p in document["data"]["projects"]}
    assert "mirror" in names


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
    assert Container().manifest().projects


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

    def test_a_nested_init_does_not_inherit_the_enclosing_workspace(
        self, empty_workspace: Path
    ):
        # `init` provisions from the workspace it is creating - the bundled
        # manifest, until the new workspace has a config of its own. Walking
        # up would answer a fresh nested init with the *enclosing* workspace's
        # file, and the new workspace would be built from an override its own
        # config does not carry.
        config = Path(WorkspaceLayout(empty_workspace).config_file)
        config.write_text('default_group = "solo"\n[groups]\nsolo = ["cangjie_test"]\n')

        result = runner.invoke(
            cli, ["init", str(empty_workspace / "inner"), "--dry-run"]
        )

        assert result.exit_code == 0
        assert "cangjie_test" not in result.output
        # The bundled default group is what a fresh workspace gets.
        assert "cangjie_compiler" in result.output

    def test_re_running_on_the_workspace_itself_is_supported(
        self, empty_workspace: Path
    ):
        result = runner.invoke(cli, ["init", str(empty_workspace), "--dry-run"])

        assert result.exit_code == 0


class TestWhatInitProvisionsFrom:
    def test_a_fresh_workspace_provisions_from_the_bundled_manifest(
        self, tmp_path: Path
    ):
        # Container level: `manifest_for_init` reads the workspace being
        # created, not the nearest one a walk up would find.
        config = Path(WorkspaceLayout(tmp_path).config_file)
        config.parent.mkdir(parents=True)
        config.write_text('default_group = "solo"\n[groups]\nsolo = ["cangjie_test"]\n')

        container = Container()

        assert container.manifest_for_init(tmp_path / "inner") == container.manifest(
            None
        )

    def test_a_re_run_honours_the_workspace_it_is_reconfiguring(self, tmp_path: Path):
        # The workspace's own config counts - but only its own: this is what
        # keeps a re-run consistent with every later command run inside.
        config = Path(WorkspaceLayout(tmp_path).config_file)
        config.parent.mkdir(parents=True)
        config.write_text(
            "[projects.cangjie_compiler]\n"
            'upstream = "https://example.invalid/compiler.git"\n'
        )

        container = Container()

        effective = container.manifest_for_init(tmp_path)
        assert (
            next(
                project.upstream_url
                for project in effective.projects
                if project.name == "cangjie_compiler"
            )
            == "https://example.invalid/compiler.git"
        )


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
            p.name for p in Container().manifest().projects
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

    def test_the_transcript_arrives_in_manifest_order_under_verbose(
        self, empty_workspace: Path
    ):
        # Every project of the manifest is probed, one git invocation each;
        # the fan-out decides when they run, not in what order they print.
        # The whole manifest is more labels than this test needs, so the
        # assertion is on the relative order of two of them.
        for name in ("cangjie_compiler", "cangjie_runtime"):
            Path(WorkspaceLayout(empty_workspace).object_store(name)).mkdir(
                parents=True
            )

        result = runner.invoke(cli, ["status", str(empty_workspace), "-v"])

        stderr = result.stderr
        compiler = stderr.index("$ git")
        runtime = stderr.index("cangjie_runtime", compiler)
        assert stderr.index("cangjie_compiler", compiler) < runtime

    def test_verbose_does_not_slow_the_fan_out(
        self, monkeypatch: pytest.MonkeyPatch, empty_workspace: Path
    ):
        # The contract the help text now states: -v changes what is shown,
        # never what is done. Pinned at the seam rather than by timing, so it
        # cannot flake: `report_status` is built through the container, and
        # the job count it performs with is visible there.
        seen: dict[str, int] = {}
        real = Container.report_status
        default = DEFAULT_QUERY_JOBS

        def spy(
            self: Container, *, verbose: bool = False, manifest: Manifest
        ) -> object:
            use_case = real(self, verbose=verbose, manifest=manifest)
            perform = use_case.perform

            def watched(*args: Any, **kwargs: Any):
                jobs = kwargs.get("jobs")
                seen["jobs"] = default if jobs is None else jobs
                return perform(*args, **kwargs)

            monkeypatch.setattr(use_case, "perform", watched)
            return use_case

        monkeypatch.setattr(Container, "report_status", spy)
        runner.invoke(cli, ["status", str(empty_workspace), "-v"])

        assert seen["jobs"] == DEFAULT_QUERY_JOBS

    def test_status_resolves_the_workspace_config_exactly_once(
        self, monkeypatch: pytest.MonkeyPatch, empty_workspace: Path
    ):
        # The CLI resolves the manifest for the transcript labels and hands
        # the same instance to the use case: a second resolution would let
        # the file change in between, and the report could disagree with the
        # labels it was flushed under.
        calls = 0
        real = Container.manifest

        def counted(self: Container, start: Path | None = None) -> object:
            nonlocal calls
            calls += 1
            return real(self, start)

        monkeypatch.setattr(Container, "manifest", counted)
        result = runner.invoke(cli, ["status", str(empty_workspace)])

        assert result.exit_code == 0
        assert calls == 1

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


@pytest.mark.usefixtures("git_available")
class TestBranchNew:
    @pytest.fixture
    def provisioned(self, tmp_path: Path) -> Path:
        """A workspace holding one project of the bundled manifest.

        Filled from a `file://` upstream: `branch new` uses no network, so the
        URL a store came from is none of its business.
        """
        root = tmp_path / "ws"
        layout = WorkspaceLayout(root)
        Path(layout.bare_dir).mkdir(parents=True)
        provision_object_store(
            HostExecutor(),
            Path(layout.object_store("cangjie_compiler")),
            Project(
                name="cangjie_compiler",
                role=ProjectRole.BUILDABLE,
                upstream_url=make_upstream(tmp_path / "upstream"),
                default_branch="main",
            ),
        )
        return root

    def test_it_refuses_outside_a_workspace(self, tmp_path: Path):
        # Act
        result = runner.invoke(
            cli, ["branch", "new", "fix/ice", "--workspace", str(tmp_path)]
        )

        # Assert
        assert isinstance(result.exception, PreconditionError)
        assert PreconditionError.exit_code == 3  # preconditions unmet

    def test_a_workspace_with_no_projects_names_the_fix(self, empty_workspace: Path):
        # Act
        result = runner.invoke(
            cli, ["branch", "new", "fix/ice", "--workspace", str(empty_workspace)]
        )

        # Assert
        assert isinstance(result.exception, PreconditionError)
        assert "cjdev init" in (result.exception.remedy or "")

    def test_the_short_flag_names_the_workspace_too(self, empty_workspace: Path):
        # The workspace is context, not the subject, so it arrives as an
        # option - and the short spelling reaches the same walk-up.
        # Act
        result = runner.invoke(
            cli, ["branch", "new", "fix/ice", "-w", str(empty_workspace)]
        )

        # Assert
        assert isinstance(result.exception, PreconditionError)
        assert "cjdev init" in (result.exception.remedy or "")

    def test_the_workspace_is_no_longer_a_positional_argument(self):
        # The second positional lands on no parameter at all: the parser
        # refuses the invocation before any code of ours runs. What is
        # pinned here is the usage line - the shape is ours - not the
        # parser's error wording, which a typer upgrade may reword.
        result = runner.invoke(cli, ["branch", "new", "fix/ice", "ws"])

        # Assert
        assert result.exit_code == 2
        assert "branch new [OPTIONS] {branch_set}" in result.output

    def test_a_name_git_would_refuse_creates_nothing(self, provisioned: Path):
        # Act
        result = runner.invoke(
            cli, ["branch", "new", "fix/../escape", "--workspace", str(provisioned)]
        )

        # Assert
        assert isinstance(result.exception, UsageError)
        assert UsageError.exit_code == 2  # the invocation itself is wrong
        assert sorted(p.name for p in provisioned.iterdir()) == [".cjdev"]

    def test_it_runs_with_no_terminal_to_ask_at(
        self, provisioned: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange: the whole input is the name, so unlike `init` there is no
        # question this could fail to ask.
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: False))

        # Act
        result = runner.invoke(
            cli, ["branch", "new", "fix/ice", "--workspace", str(provisioned)]
        )

        # Assert
        assert result.exit_code == 0, result.output
        assert (provisioned / "fix-ice" / "cangjie_compiler" / "README").is_file()

    def test_the_report_is_available_to_something_that_is_not_a_person(
        self, provisioned: Path
    ):
        # Act
        result = runner.invoke(
            cli, ["branch", "new", "fix/ice", "--workspace", str(provisioned), "--json"]
        )

        # Assert
        document = json.loads(result.stdout)
        assert document["schema"] == SCHEMA
        assert document["ok"]
        assert document["data"]["branch"] == "fix/ice"
        assert document["data"]["projects"] == [
            {
                "name": "cangjie_compiler",
                "path": str(provisioned / "fix-ice" / "cangjie_compiler"),
                "outcome": "created",
                "error": None,
            }
        ]

    def test_a_failed_checkout_is_counted_in_the_summary(
        self, provisioned: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange: the closing line is what a pipe has instead of the table,
        # so the checkout itself has to drive it - only the rollback takes
        # the transcript.
        real = Container.new_branch_set

        def failing(self: Container, **kwargs: Any) -> NewBranchSet:
            use_case = real(self, **kwargs)

            def add(executor: Executor, enrolment: Enrolment) -> None:
                raise RuntimeError("disk full")

            monkeypatch.setattr(use_case, "_add", add)
            return use_case

        monkeypatch.setattr(Container, "new_branch_set", failing)

        # Act
        result = runner.invoke(
            cli, ["branch", "new", "fix/ice", "--workspace", str(provisioned)]
        )

        # Assert
        assert result.exit_code == 1
        assert "1 failed" in result.output
        assert "nothing to do" not in result.output
        assert "[1/1] cangjie_compiler" in result.stderr

    def test_what_it_ran_is_in_the_workspace_log(self, provisioned: Path):
        # Act
        runner.invoke(
            cli, ["branch", "new", "fix/ice", "--workspace", str(provisioned)]
        )

        # Assert: the log is always on, because "what did that actually run?"
        # is only ever asked afterwards.
        log = Path(WorkspaceLayout(provisioned).command_log).read_text()
        assert "worktree add" in log
