"""The ADR index is derived data (ADR-0024): a test fails when it is stale.

The same shape `ruff format --check` has - a generated file nobody edits by hand,
and a CI job that says so. The generator itself is tested here too, against
synthetic ADRs in a tmp_path: what lands in the table, what a malformed file
refuses with, and that --check fails exactly when the file differs.

The generator is a standalone script under tools/, reached by path rather than
imported as a package: it is repo tooling, not part of the shipped cjdev, and
the test loads it exactly the way `python tools/adr_index.py` runs it.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "adr_index.py"

VALID = """\
# ADR-0031: <decision>

Status: accepted, 2026-10-06. Closes #31.

## Context

Body.
"""


def load_generator(monkeypatch: pytest.MonkeyPatch, adr_dir: Path):
    """The generator module, pointed at a synthetic docs/adr/ in a tmp_path."""
    spec = importlib.util.spec_from_file_location("adr_index_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    index = adr_dir / "README.md"
    monkeypatch.setattr(module, "ADR_DIR", adr_dir, raising=True)
    monkeypatch.setattr(module, "INDEX", index, raising=True)
    return module, index


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )


def test_index_is_fresh() -> None:
    """The committed docs/adr/README.md is exactly what the generator writes."""
    result = run_script("--check")
    assert result.returncode == 0, (
        f"docs/adr/README.md is stale.\n{result.stderr}\nRun: python tools/adr_index.py"
    )


def test_a_written_index_passes_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generator, _ = load_generator(monkeypatch, tmp_path)
    generator.main([])
    assert generator.main(["--check"]) == 0


def test_a_stale_index_fails_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generator, _ = load_generator(monkeypatch, tmp_path)
    (tmp_path / "0031-decision.md").write_text(VALID, encoding="utf-8")
    (tmp_path / "README.md").write_text("stale\n", encoding="utf-8")
    assert generator.main(["--check"]) == 1


def test_the_table_carries_number_title_and_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generator, index = load_generator(monkeypatch, tmp_path)
    (tmp_path / "0031-decision.md").write_text(
        VALID.replace("<decision>", "A decision made"), encoding="utf-8"
    )
    (tmp_path / "0007-earlier.md").write_text(
        VALID.replace("ADR-0031", "ADR-0007")
        .replace("Closes #31", "Closes #7")
        .replace("accepted, 2026-10-06.", "accepted; superseded by ADR-0031."),
        encoding="utf-8",
    )
    generator.main([])
    rendered = index.read_text(encoding="utf-8")
    # Rows are ordered by number, not by file name: the ADR added second is first.
    assert rendered.index("[0007]") < rendered.index("[0031]")
    assert "| [0031](0031-decision.md) | A decision made | accepted |" in rendered
    assert "superseded by ADR-0031" in rendered


def test_a_malformed_adr_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generator, _ = load_generator(monkeypatch, tmp_path)
    # A file whose name and heading disagree: the refusal must name the file,
    # because the fix is renaming one of the two.
    (tmp_path / "0031-decision.md").write_text(
        VALID.replace("ADR-0031", "ADR-0099"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match=r"0031-decision\.md"):
        generator.render_index()


def test_a_missing_status_line_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generator, _ = load_generator(monkeypatch, tmp_path)
    (tmp_path / "0031-decision.md").write_text(
        "# ADR-0031: decision\n\nNo status line at all.\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match=r"0031-decision\.md"):
        generator.render_index()


def test_a_duplicated_number_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generator, _ = load_generator(monkeypatch, tmp_path)
    # Two files with the same number: a copy-paste or rename mistake, and the
    # old dict-based index silently dropped one. The refusal must name both
    # files, because one of them has to go or be renumbered.
    (tmp_path / "0031-decision.md").write_text(VALID, encoding="utf-8")
    (tmp_path / "0031-duplicate.md").write_text(VALID, encoding="utf-8")
    with pytest.raises(ValueError, match=r"0031-decision\.md and 0031-duplicate\.md"):
        generator.render_index()
