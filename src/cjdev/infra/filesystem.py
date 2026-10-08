"""Changing the workspace tree, or saying what would change it."""

import os
import shutil
from collections.abc import Callable
from pathlib import Path, PurePath
from typing import final

from cjdev.application.ports import FileSystem
from cjdev.errors import PreconditionError


@final
class HostFileSystem:
    def mkdir(self, path: PurePath) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)

    def write_text(self, path: PurePath, text: str) -> None:
        Path(path).write_text(text, encoding="utf-8")

    def remove(self, path: PurePath) -> None:
        target = Path(path)
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()

    def symlink(self, link: PurePath, target: PurePath) -> None:
        # Staged beside the link and moved over it: `symlink_to` refuses to
        # replace an existing entry, and unlink-then-create leaves a window in
        # which the path is not a link at all.
        path = Path(link)
        path.parent.mkdir(parents=True, exist_ok=True)
        staged = path.parent / f".{path.name}.cjdev{os.getpid()}"
        staged.unlink(missing_ok=True)
        staged.symlink_to(target)
        staged.replace(path)

    def copy(self, source: PurePath, into: PurePath) -> None:
        destination = Path(into)
        destination.mkdir(parents=True, exist_ok=True)
        # copy2 rather than copy: an installed binary that lost its mtime
        # looks rebuilt to everything that compares timestamps.
        shutil.copy2(source, destination / Path(source).name)

    def move(self, source: PurePath, destination: PurePath) -> None:
        origin, there = Path(source), Path(destination)
        if not origin.exists() and not origin.is_symlink():
            return
        if there.exists() or there.is_symlink():
            raise PreconditionError(
                f"{there} is already there; moving {origin} onto it would mix "
                f"two builds.",
                remedy=f"delete whichever of {origin} and {there} is stale",
            )
        there.parent.mkdir(parents=True, exist_ok=True)
        origin.rename(there)


@final
class DryRunFileSystem:
    def __init__(self, emit: Callable[[str], None]) -> None:
        self._emit = emit

    def mkdir(self, path: PurePath) -> None:
        self._emit(f"mkdir -p {path}")

    def write_text(self, path: PurePath, text: str) -> None:
        self._emit(f"write {path} ({len(text)} bytes)")

    def remove(self, path: PurePath) -> None:
        self._emit(f"rm -rf {path}")

    def symlink(self, link: PurePath, target: PurePath) -> None:
        self._emit(f"ln -sfn {target} {link}")

    def copy(self, source: PurePath, into: PurePath) -> None:
        self._emit(f"cp {source} {into}/")

    def move(self, source: PurePath, destination: PurePath) -> None:
        self._emit(f"mv {source} {destination}")


def build_file_system(*, dry_run: bool, emit: Callable[[str], None]) -> FileSystem:
    return DryRunFileSystem(emit) if dry_run else HostFileSystem()
