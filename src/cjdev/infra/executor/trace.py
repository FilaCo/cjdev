"""Watching commands go by: the live echo, the file record and the step feed.

Three decorators rather than one, because they answer to three different
switches - `-v`, the workspace log, and the progress display - and a single
class doing all three would have to be told which parts to keep quiet.
"""

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import final

from cjdev.application.ports import Command, Completed, Executor
from cjdev.errors import CommandError


def render(command: Command) -> str:
    return f"{' '.join(command.argv)}  # {_short(command.cwd)}"


def _short(cwd: Path) -> str:
    """Relative to where the user is standing, when that is shorter.

    An absolute path inside a workspace is long enough to wrap twice, which
    buries the command it is annotating.
    """
    try:
        relative = os.path.relpath(cwd, Path.cwd())
    except ValueError:
        return str(cwd)
    return relative if not relative.startswith("..") else str(cwd)


@final
class EchoExecutor:
    """`-v`: every invocation on screen as it happens."""

    def __init__(self, inner: Executor, emit: Callable[[str], None]) -> None:
        self._inner = inner
        self._emit = emit

    def run(self, command: Command, *, check: bool = True) -> Completed:
        self._emit(f"$ {render(command)}")
        try:
            result = self._inner.run(command, check=check)
        except CommandError as failure:
            # The exit status of *every* invocation is wanted, and with
            # check=True the common case leaves by this path.
            self._emit(f"  exited {failure.command_exit_code}")
            raise
        if not result.ok:
            self._emit(f"  exited {result.exit_code}")
        return result


@final
class RecordingExecutor:
    """The durable half: argv, cwd, exit status and duration into the log.

    Always on for a mutating command, whatever `-v` says. The point is the
    question asked after the fact - "what did it actually run against my
    repositories?" - which nobody thinks to enable in advance.

    One line per command, written when it finishes rather than a line before
    and a line after. Under `-j` a start line and an exit line from different
    projects interleave, and a reader cannot tell which exit belongs to which
    command; a single completed line cannot be misread that way.
    """

    def __init__(
        self,
        inner: Executor,
        record: Callable[[str], None],
        base: Path | None = None,
    ) -> None:
        self._inner = inner
        self._record = record
        self._base = base
        """The workspace root, so a `cwd` reads `.cjdev/bare/x.git` rather
        than eighty characters of absolute path repeated on every line."""

    def run(self, command: Command, *, check: bool = True) -> Completed:
        began = time.monotonic()
        try:
            result = self._inner.run(command, check=check)
        except CommandError as failure:
            self._write(command, failure.command_exit_code, began)
            self._write_output(failure.output)
            raise
        self._write(command, result.exit_code, began)
        if not result.ok:
            self._write_output(result.stderr or result.stdout)
        return result

    def _write(self, command: Command, exit_code: int, began: float) -> None:
        status = "ok " if exit_code == 0 else f"E{exit_code}"
        took = time.monotonic() - began
        self._record(
            f"{status} {took:6.2f}s  {' '.join(command.argv)}"
            f"  # {self._where(command.cwd)}"
        )

    def _write_output(self, output: str) -> None:
        for line in output.strip().splitlines():
            self._record(f"          | {line}")

    def _where(self, cwd: Path) -> str:
        if self._base is None:
            return str(cwd)
        relative = os.path.relpath(cwd, self._base)
        return str(cwd) if relative.startswith("..") else relative


@final
class StepExecutor:
    """Tells the progress display what the current command is doing.

    Derived from the command rather than announced by the caller, so a unit of
    work that runs six commands shows six steps without carrying a callback
    through its own body.
    """

    def __init__(self, inner: Executor, report: Callable[[str], None]) -> None:
        self._inner = inner
        self._report = report

    def run(self, command: Command, *, check: bool = True) -> Completed:
        self._report(command.what or " ".join(command.argv[:2]))
        return self._inner.run(command, check=check)
