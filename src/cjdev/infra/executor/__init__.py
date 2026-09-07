"""Assembling the executor stack.

The caller gets one `Executor` and never learns that it is dry-run wrapping
step-reporting wrapping echo wrapping recording wrapping the host, which is
what earns this a folder over a module.

The order is the point. Recording sits innermost so the log holds what really
ran and what it really exited with, and dry-run sits outermost so a command it
declines to run is never recorded as having run.
"""

from collections.abc import Callable
from pathlib import Path

from cjdev.application.ports import Executor

from .dry_run import DryRunExecutor
from .host import HostExecutor
from .trace import EchoExecutor, RecordingExecutor, StepExecutor

__all__ = ["build_executor"]


def build_executor(
    *,
    dry_run: bool = False,
    verbose: bool = False,
    emit: Callable[[str], None],
    record: Callable[[str], None] | None = None,
    record_base: Path | None = None,
    report_step: Callable[[str], None] | None = None,
) -> Executor:
    executor: Executor = HostExecutor()
    if record is not None:
        executor = RecordingExecutor(executor, record, record_base)
    if verbose:
        executor = EchoExecutor(executor, emit)
    if report_step is not None:
        executor = StepExecutor(executor, report_step)
    if dry_run:
        executor = DryRunExecutor(executor, emit)
    return executor
