"""Tree mutations on the progress display and in the workspace log."""

from pathlib import Path

import pytest

from cjdev.errors import PreconditionError
from cjdev.infra.filesystem import HostFileSystem, TracedFileSystem


def test_a_move_is_a_step_and_a_log_line_relative_to_the_workspace(tmp_path: Path):
    # Arrange
    (tmp_path / "here").mkdir()
    steps: list[str] = []
    lines: list[str] = []
    fs = TracedFileSystem(
        HostFileSystem(), report=steps.append, record=lines.append, base=tmp_path
    )

    # Act
    fs.move(tmp_path / "here", tmp_path / ".cjdev" / "there")

    # Assert
    assert steps == ["moving here"]
    (line,) = lines
    assert line.startswith("ok ")
    assert line.endswith("mv here .cjdev/there")


def test_a_refused_mutation_is_logged_with_its_reason_and_still_raised(
    tmp_path: Path,
):
    # Arrange: the log is read after the fact, when the reason is the question.
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    lines: list[str] = []
    fs = TracedFileSystem(
        HostFileSystem(), report=lambda _: None, record=lines.append, base=tmp_path
    )

    # Act / Assert
    with pytest.raises(PreconditionError):
        fs.move(tmp_path / "a", tmp_path / "b")
    assert lines[0].startswith("err")
    assert "already there" in lines[1]
