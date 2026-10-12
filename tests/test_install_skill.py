"""The agent skill: what ships, where it is installed, and that it still
describes the CLI it ships with."""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from typer.main import get_command
from typer.testing import CliRunner

from cjdev.application.install_skill import SKILL_NAME, InstallSkill, Outcome
from cjdev.bootstrap import _read_file
from cjdev.cli import cli
from cjdev.cli._output import SCHEMA
from cjdev.infra.filesystem import build_file_system
from cjdev.infra.skill import load_bundled_skill

runner = CliRunner()
SKILL = load_bundled_skill()


def _install(emitted: list[str] | None = None) -> InstallSkill:
    if emitted is None:
        fs = build_file_system(dry_run=False, emit=print)
    else:
        fs = build_file_system(dry_run=True, emit=emitted.append)
    return InstallSkill(file_system=fs, skill="the skill", read=_read_file)


def _frontmatter() -> dict[str, str]:
    block = SKILL.split("---\n")[1]
    return dict(line.split(": ", 1) for line in block.splitlines())


def _commands(group: Any, prefix: tuple[str, ...] = ()) -> Iterator[tuple[str, Any]]:
    for name, command in getattr(group, "commands", {}).items():
        path = (*prefix, name)
        yield " ".join(path), command
        yield from _commands(command, path)


COMMANDS = dict(_commands(get_command(cli)))


class TestInstallSkill:
    def test_a_fresh_directory_gets_the_skill(self, tmp_path: Path):
        # Act
        target, outcome = _install().perform(tmp_path)

        # Assert
        assert target == tmp_path / SKILL_NAME / "SKILL.md"
        assert outcome is Outcome.INSTALLED
        assert target.read_text() == "the skill"

    def test_an_identical_skill_is_left_alone(self, tmp_path: Path):
        # Arrange
        _install().perform(tmp_path)

        # Act
        _, outcome = _install().perform(tmp_path)

        # Assert
        assert outcome is Outcome.CURRENT

    def test_an_older_skill_is_replaced(self, tmp_path: Path):
        # Arrange
        (tmp_path / SKILL_NAME).mkdir()
        (tmp_path / SKILL_NAME / "SKILL.md").write_text("an older skill")

        # Act
        target, outcome = _install().perform(tmp_path)

        # Assert
        assert outcome is Outcome.UPDATED
        assert target.read_text() == "the skill"

    def test_a_dry_run_writes_nothing_and_says_what_it_would(self, tmp_path: Path):
        # Arrange
        emitted: list[str] = []

        # Act
        _, outcome = _install(emitted).perform(tmp_path)

        # Assert
        assert outcome is Outcome.INSTALLED
        assert not (tmp_path / SKILL_NAME).exists()
        assert any("SKILL.md" in line for line in emitted)


class TestBundledSkill:
    def test_the_name_matches_the_directory_it_is_installed_into(self):
        # Act / Assert: the Agent Skills format requires the two to match.
        assert _frontmatter()["name"] == SKILL_NAME

    def test_the_description_fits_the_agent_skills_limit(self):
        # Act
        description = _frontmatter()["description"]

        # Assert
        assert 0 < len(description) <= 1024

    def test_every_command_it_names_exists(self):
        # Arrange
        named = re.findall(r"(?:`|^)cjdev ([a-z]+(?: [a-z]+)?)", SKILL, re.M)

        # Act: the second word may be an argument rather than a subcommand.
        missing = {n for n in named if n not in COMMANDS}
        missing -= {n for n in missing if n.split()[0] in COMMANDS}

        # Assert
        assert named
        assert not missing

    def test_the_json_commands_it_lists_are_the_ones_with_json(self):
        # Arrange
        with_json = {
            path
            for path, command in COMMANDS.items()
            if any("--json" in getattr(p, "opts", ()) for p in command.params)
        }
        line = next(ln for ln in SKILL.splitlines() if "`--json` where it exists" in ln)

        # Act
        listed = set(re.findall(r"`([a-z ]+)`", line.split(":", 1)[1]))

        # Assert
        assert listed == with_json

    def test_the_schema_it_tells_agents_to_pin_is_the_current_one(self):
        # Act / Assert
        assert f"Stop if `schema` is not `{SCHEMA}`" in SKILL


class TestCli:
    def test_show_prints_the_skill_verbatim(self):
        # Act
        result = runner.invoke(cli, ["skill", "show"])

        # Assert
        assert result.exit_code == 0
        assert result.stdout == SKILL

    def test_install_writes_into_the_named_directory(self, tmp_path: Path):
        # Act
        result = runner.invoke(cli, ["skill", "install", "--dir", str(tmp_path)])

        # Assert
        assert result.exit_code == 0
        assert (tmp_path / SKILL_NAME / "SKILL.md").read_text() == SKILL
