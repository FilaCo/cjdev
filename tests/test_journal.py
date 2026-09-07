"""The workspace log: what a mutating command leaves behind for later."""

from pathlib import Path

import pytest

from cjdev.application.ports import Command
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import CommandError
from cjdev.infra.executor import build_executor
from cjdev.infra.journal import MAX_BYTES, CommandJournal, open_journal


def a_command(argv: tuple[str, ...], cwd: Path) -> Command:
    return Command(argv=argv, cwd=cwd, mutates=True)


class TestRecording:
    def test_one_complete_line_per_command(self, tmp_path: Path):
        # A start line and an exit line would interleave under -j, leaving a
        # reader unable to tell which exit belonged to which command.
        written: list[str] = []
        executor = build_executor(emit=print, record=written.append)

        executor.run(a_command(("echo", "hi"), tmp_path))

        assert len(written) == 1
        assert written[0].startswith("ok ")
        assert "echo hi" in written[0]

    def test_a_failure_records_its_code_and_its_output(self, tmp_path: Path):
        written: list[str] = []
        executor = build_executor(emit=print, record=written.append)

        with pytest.raises(CommandError):
            executor.run(a_command(("sh", "-c", "echo boom >&2; exit 3"), tmp_path))

        assert written[0].startswith("E3 ")
        assert any("boom" in line for line in written[1:])

    def test_the_cwd_is_relative_to_the_workspace(self, tmp_path: Path):
        # An absolute path inside a workspace is most of the line, repeated
        # identically on every one of them.
        inside = tmp_path / ".cjdev" / "bare"
        inside.mkdir(parents=True)
        written: list[str] = []
        executor = build_executor(
            emit=print, record=written.append, record_base=tmp_path
        )

        executor.run(a_command(("echo", "hi"), inside))

        assert written[0].endswith("# .cjdev/bare")

    def test_a_dry_run_records_nothing(self, tmp_path: Path):
        written: list[str] = []
        executor = build_executor(dry_run=True, emit=print, record=written.append)

        executor.run(a_command(("rm", "-rf", "/"), tmp_path))

        assert written == []


class TestTheFile:
    def test_it_lands_under_the_marker_and_carries_a_header(self, tmp_path: Path):
        with open_journal(tmp_path, ["init", "."]) as journal:
            journal.write("ok  0.01s  git status")

        log = Path(WorkspaceLayout(tmp_path).command_log)
        assert log.is_file()
        lines = log.read_text(encoding="utf-8").splitlines()
        assert "cjdev init ." in lines[0]
        assert lines[1].endswith("git status")

    def test_runs_accumulate_rather_than_overwrite(self, tmp_path: Path):
        for _ in range(2):
            with open_journal(tmp_path, ["init", "."]) as journal:
                journal.write("something")

        log = Path(WorkspaceLayout(tmp_path).command_log)
        assert log.read_text(encoding="utf-8").count("cjdev init") == 2

    def test_a_large_log_is_rotated_to_one_backup(self, tmp_path: Path):
        log = Path(WorkspaceLayout(tmp_path).command_log)
        log.parent.mkdir(parents=True)
        log.write_text("x" * MAX_BYTES, encoding="utf-8")

        open_journal(tmp_path, ["init", "."]).close()

        assert log.with_suffix(".log.1").is_file()
        assert "cjdev init" in log.read_text(encoding="utf-8")

    def test_an_unwritable_location_is_not_an_error(self, tmp_path: Path):
        # A full or read-only disk must not be the reason `cjdev init` fails.
        blocked = tmp_path / "not-a-dir"
        blocked.write_text("")

        journal = CommandJournal(blocked / ".cjdev" / "log" / "cjdev.log")
        journal.write("swallowed")
        journal.close()
