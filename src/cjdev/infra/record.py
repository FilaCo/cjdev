"""A branch set's record, `.cjdev/state/<set>.toml`, through `tomlkit`.

Rendered into the text already there rather than from scratch: each command
owns its own table, and a write of the profile must not drop a table a newer
cjdev added beside it.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path, PurePath
from typing import Any

import tomlkit

from cjdev.application.ports import FileSystem
from cjdev.domain.build import Profile
from cjdev.domain.dependencies import Selection
from cjdev.domain.record import BranchSetRecord, Task
from cjdev.errors import PreconditionError

HEADER = "Written by cjdev: what it remembers about this branch set."


def read_record(path: PurePath) -> BranchSetRecord:
    text = _read(path)
    if not text:
        return BranchSetRecord()
    document = _parse(text, path)
    return BranchSetRecord(
        profile=_profile(document, path),
        task=_task(document, path),
        dependencies=_dependencies(document, path),
    )


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
    """Merge profile and task fields into the existing record."""
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


def _dependencies(document: Any, path: PurePath) -> dict[tuple[str, str], Selection]:
    result = {}
    units = document.get("deps", {})
    error = PreconditionError(
        f"{path}: expected [deps.UNIT.DEPENDENCY] with a ref and optional upstream."
    )
    if not isinstance(units, dict):
        raise error
    for unit, sources in units.items():
        if not isinstance(sources, dict):
            raise error
        for name, data in sources.items():
            if not isinstance(data, dict):
                raise error
            ref, upstream = data.get("ref"), data.get("upstream")
            if not isinstance(ref, str) or not ref.strip():
                raise error
            if upstream is not None and (
                not isinstance(upstream, str) or not upstream.strip()
            ):
                raise error
            result[unit, name] = Selection(ref, upstream)
    return result


class RecordWriter:
    """Serialize edits sharing a branch-set record and publish them atomically."""

    def __init__(
        self, fs: FileSystem, lock: Callable[[PurePath], AbstractContextManager[None]]
    ) -> None:
        self._fs = fs
        self._lock = lock

    def save(self, record: BranchSetRecord, path: PurePath) -> None:
        self._fs.mkdir(path.parent)
        with self._lock(path.with_suffix(".lock")):
            self._fs.replace_text(path, render_record(record, path))

    def edit_dependency(
        self,
        path: PurePath,
        unit: str,
        name: str,
        decide: Callable[[Selection | None], Selection | None],
    ) -> Selection | None:
        self._fs.mkdir(path.parent)
        with self._lock(path.with_suffix(".lock")):
            current = _read(path)
            document: Any = _parse(current, path) if current else tomlkit.document()
            previous = _dependencies(document, path).get((unit, name))
            selected = decide(previous)
            if selected == previous:
                return selected
            if not current:
                document.add(tomlkit.comment(HEADER))
            deps = document.setdefault("deps", {})
            sources = deps.setdefault(unit, {})
            if selected is None:
                del sources[name]
                if not sources:
                    del deps[unit]
                if not deps:
                    del document["deps"]
            else:
                choice = sources.setdefault(name, {})
                choice["ref"] = selected.ref
                if selected.upstream is not None:
                    choice["upstream"] = selected.upstream
            self._fs.replace_text(path, tomlkit.dumps(document))
            return selected
