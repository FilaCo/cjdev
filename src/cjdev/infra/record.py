"""A branch set's record, `.cjdev/state/<set>.toml`, through `tomlkit`.

Rendered into the text already there rather than from scratch: each command
owns its own table, and a write of the profile must not drop a table a newer
cjdev added beside it.
"""

from pathlib import Path, PurePath
from typing import Any

import tomlkit

from cjdev.domain.build import Profile
from cjdev.domain.record import BranchSetRecord, Task
from cjdev.errors import PreconditionError

HEADER = "Written by cjdev: what it remembers about this branch set."


def read_record(path: PurePath) -> BranchSetRecord:
    text = _read(path)
    if not text:
        return BranchSetRecord()
    document = _parse(text, path)
    return BranchSetRecord(profile=_profile(document, path), task=_task(document, path))


def _profile(document: Any, path: PurePath) -> Profile | None:
    build = document.get("build", {})
    profile = build.get("profile") if isinstance(build, dict) else None
    if profile is None:
        return None
    try:
        return Profile(str(profile))
    except ValueError:
        raise PreconditionError(
            f"{path} records profile {str(profile)!r}. "
            f"Expected: {', '.join(member.value for member in Profile)}.",
            remedy=f"delete {path}",
        ) from None


def _task(document: Any, path: PurePath) -> Task | None:
    task = document.get("task")
    if task is None:
        return None
    home = task.get("home") if isinstance(task, dict) else 0
    issue = task.get("issue") if isinstance(task, dict) else 0
    if not isinstance(home, str | None) or not isinstance(issue, str | None):
        raise PreconditionError(
            f"{path}: [task] is a table whose home and issue are strings.",
            remedy=f"delete {path}",
        )
    return Task(
        home=None if home is None else str(home),
        issue=None if issue is None else str(issue),
    )


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
    if record.task is not None:
        if "task" not in document:
            document["task"] = tomlkit.table()
        # Key by key rather than a fresh table: what a later command keeps
        # under [task], the PRs of #47, outlives attaching an issue.
        task: Any = document["task"]
        for key, value in (("issue", record.task.issue), ("home", record.task.home)):
            if value is not None:
                task[key] = value
            elif key in task:
                del task[key]
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
