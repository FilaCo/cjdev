"""Changing the workspace tree, or saying what would change it."""

import os
import shutil
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
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


@final
class TracedFileSystem:
    """A tree mutation on the progress display and in the workspace log, the
    way `StepExecutor` and `RecordingExecutor` put a command there.

    Without it a build's scratch moves, and the directories it absorbs or the
    links it removes, happen between two logged commands with no trace of
    their own.
    """

    def __init__(
        self,
        inner: FileSystem,
        *,
        report: Callable[[str], None],
        record: Callable[[str], None] | None = None,
        base: Path | None = None,
    ) -> None:
        self._inner = inner
        self._report = report
        self._record = record
        self._base = base

    def mkdir(self, path: PurePath) -> None:
        with self._recorded(f"creating {path.name}", f"mkdir -p {self._at(path)}"):
            self._inner.mkdir(path)

    def write_text(self, path: PurePath, text: str) -> None:
        with self._recorded(f"writing {path.name}", f"write {self._at(path)}"):
            self._inner.write_text(path, text)

    def remove(self, path: PurePath) -> None:
        with self._recorded(f"removing {path.name}", f"rm -rf {self._at(path)}"):
            self._inner.remove(path)

    def symlink(self, link: PurePath, target: PurePath) -> None:
        line = f"ln -sfn {target} {self._at(link)}"
        with self._recorded(f"linking {link.name}", line):
            self._inner.symlink(link, target)

    def copy(self, source: PurePath, into: PurePath) -> None:
        line = f"cp {self._at(source)} {self._at(into)}/"
        with self._recorded(f"copying {source.name}", line):
            self._inner.copy(source, into)

    def move(self, source: PurePath, destination: PurePath) -> None:
        line = f"mv {self._at(source)} {self._at(destination)}"
        with self._recorded(f"moving {source.name}", line):
            self._inner.move(source, destination)

    @contextmanager
    def _recorded(self, step: str, line: str) -> Iterator[None]:
        self._report(step)
        began = time.monotonic()
        try:
            yield
        except Exception as failure:
            self._write("err", began, line)
            if self._record is not None:
                self._record(f"          | {failure}")
            raise
        self._write("ok ", began, line)

    def _write(self, status: str, began: float, line: str) -> None:
        if self._record is not None:
            self._record(f"{status} {time.monotonic() - began:6.2f}s  {line}")

    def _at(self, path: PurePath) -> str:
        if self._base is None:
            return str(path)
        relative = os.path.relpath(path, self._base)
        return str(path) if relative.startswith("..") else relative


def build_file_system(
    *,
    dry_run: bool,
    emit: Callable[[str], None],
    report_step: Callable[[str], None] | None = None,
    record: Callable[[str], None] | None = None,
    record_base: Path | None = None,
) -> FileSystem:
    if dry_run:
        return DryRunFileSystem(emit)
    if report_step is None and record is None:
        return HostFileSystem()
    return TracedFileSystem(
        HostFileSystem(),
        report=report_step or (lambda _: None),
        record=record,
        base=record_base,
    )
