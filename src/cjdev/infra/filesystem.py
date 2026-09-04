"""Changing the workspace tree, or saying what would change it."""

import shutil
from collections.abc import Callable
from pathlib import Path, PurePath
from typing import final

from cjdev.application.ports import FileSystem


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


def build_file_system(*, dry_run: bool, emit: Callable[[str], None]) -> FileSystem:
    return DryRunFileSystem(emit) if dry_run else HostFileSystem()
