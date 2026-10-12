"""A branch set's record, `.cjdev/state/<set>.toml`, through `tomlkit`.

Rendered into the text already there rather than from scratch: each command
owns its own table, and a write of the profile must not drop a table a newer
cjdev added beside it.
"""

from pathlib import Path, PurePath
from typing import Any

import tomlkit

from cjdev.domain.build import Profile
from cjdev.domain.record import BranchSetRecord
from cjdev.errors import PreconditionError

HEADER = "Written by cjdev: what it remembers about this branch set."


def read_record(path: PurePath) -> BranchSetRecord:
    text = _read(path)
    if not text:
        return BranchSetRecord()
    document = _parse(text, path)
    build = document.get("build", {})
    profile = build.get("profile") if isinstance(build, dict) else None
    if profile is None:
        return BranchSetRecord()
    try:
        return BranchSetRecord(profile=Profile(str(profile)))
    except ValueError:
        raise PreconditionError(
            f"{path} records profile {str(profile)!r}. "
            f"Expected: {', '.join(member.value for member in Profile)}.",
            remedy=f"delete {path}",
        ) from None


def render_record(record: BranchSetRecord, path: PurePath) -> str:
    """The file's next text. Returned rather than written, so the write goes
    through the `FileSystem` port and a dry run declines it."""
    current = _read(path)
    document = _parse(current, path) if current else tomlkit.document()
    if not current:
        document.add(tomlkit.comment(HEADER))
    if record.profile is not None:
        if "build" not in document:
            document["build"] = tomlkit.table()
        document["build"]["profile"] = record.profile.value  # type: ignore[index]
    return tomlkit.dumps(document)


def _read(path: PurePath) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _parse(text: str, path: PurePath) -> Any:
    try:
        return tomlkit.parse(text)
    except Exception as exc:  # tomlkit raises a family of parse errors
        raise PreconditionError(
            f"{path} is not valid TOML: {exc}", remedy=f"delete {path}"
        ) from exc
