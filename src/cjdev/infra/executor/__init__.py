"""Assembling the executor stack.

The caller gets one `Executor` and never learns that it is dry-run wrapping
logging wrapping the host, which is what earns this a folder over a module.
"""

from collections.abc import Callable

from cjdev.application.ports import Executor

from .dry_run import DryRunExecutor
from .host import HostExecutor
from .log import LoggingExecutor

__all__ = ["build_executor"]


def build_executor(
    *, dry_run: bool = False, verbose: bool = False, emit: Callable[[str], None]
) -> Executor:
    executor: Executor = HostExecutor()
    if verbose:
        executor = LoggingExecutor(executor, emit)
    if dry_run:
        executor = DryRunExecutor(executor, emit)
    return executor
