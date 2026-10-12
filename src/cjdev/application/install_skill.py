"""`cjdev skill install`: the bundled skill, written where an agent finds it."""

from collections.abc import Callable
from enum import Enum
from pathlib import Path, PurePath
from typing import final

from cjdev.application.ports import FileSystem

SKILL_NAME = "cjdev"
"""The directory name, which the Agent Skills format requires to match the
skill's `name`."""


class Outcome(Enum):
    INSTALLED = "installed"
    UPDATED = "updated"
    CURRENT = "current"


@final
class InstallSkill:
    def __init__(
        self,
        file_system: FileSystem,
        skill: str,
        read: Callable[[PurePath], str | None],
    ) -> None:
        self._fs = file_system
        self._skill = skill
        self._read = read

    def perform(self, skills_dir: Path) -> tuple[Path, Outcome]:
        target = skills_dir / SKILL_NAME / "SKILL.md"
        # A read, so a dry run reports the outcome the real run would have.
        current = self._read(target)
        if current == self._skill:
            return target, Outcome.CURRENT
        self._fs.mkdir(target.parent)
        self._fs.write_text(target, self._skill)
        return target, Outcome.INSTALLED if current is None else Outcome.UPDATED
