"""Printing what would run instead of running it."""

from collections.abc import Callable
from typing import final

from cjdev.application.ports import Command, Completed, Executor

from .trace import render


@final
class DryRunExecutor:
    def __init__(self, inner: Executor, emit: Callable[[str], None]) -> None:
        self._inner = inner
        self._emit = emit

    def run(self, command: Command, *, check: bool = True) -> Completed:
        # Read-only commands still run. A dry run has to inspect the world to
        # decide anything; blocking those would print a plan built on guesses
        # rather than the plan that would actually execute.
        if not command.mutates:
            return self._inner.run(command, check=check)
        self._emit(render(command))
        return Completed(command, exit_code=0, stdout="", stderr="")
