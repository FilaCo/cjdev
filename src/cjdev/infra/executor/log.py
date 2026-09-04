"""Echoing every invocation, for `-v` (UX-3)."""

import os
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
class LoggingExecutor:
    """The live half of UX-3. The durable half - a file per unit of work under
    `log/<branch-set>/` - lands with PAR-11, once there is a branch set to key
    it by; `init` runs before any exists.
    """

    def __init__(self, inner: Executor, emit: Callable[[str], None]) -> None:
        self._inner = inner
        self._emit = emit

    def run(self, command: Command, *, check: bool = True) -> Completed:
        self._emit(f"$ {render(command)}")
        try:
            result = self._inner.run(command, check=check)
        except CommandError as failure:
            # UX-3 asks for the exit status of *every* invocation, and with
            # check=True the common case leaves by this path.
            self._emit(f"  exited {failure.command_exit_code}")
            raise
        if not result.ok:
            self._emit(f"  exited {result.exit_code}")
        return result
