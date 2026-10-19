"""The agent skill that ships in the wheel (ADR-0065)."""

from importlib.resources import files

SKILL = "SKILL.md"


def load_bundled_skill() -> str:
    return (files("cjdev.infra") / "data" / SKILL).read_text(encoding="utf-8")
