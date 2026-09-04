"""Turning a report into terminal output (UX-4, UX-8, PAR-4)."""

from collections.abc import Callable
from typing import TypeVar

from rich.console import Console
from rich.text import Text

from cjdev.application.clean_workspace import CleanPlan
from cjdev.application.init_workspace import InitPlan
from cjdev.application.runner import Outcome, RunReport
from cjdev.errors import CommandError

from ._console import CANCELLED, DETAIL, MARKS, OK

T = TypeVar("T")


def render_report(
    console: Console, report: RunReport[T], *, lines: Callable[[str], tuple[str, ...]]
) -> None:
    """Rows in submission order, then each failure in full.

    `lines` supplies what a unit printed. It is rendered here, after the run,
    rather than as it happened: under `-j` the order it happened in is the
    scheduler's, and the transcript is not allowed to be (PAR-4).
    """
    for result in report.results:
        captured = lines(result.label)
        if not captured:
            continue
        console.print(result.label)
        for line in captured:
            # soft_wrap so a long path is left to the terminal instead of
            # being broken mid-word by rich's own word wrapping.
            console.print(f"  {line}", style=DETAIL, highlight=False, soft_wrap=True)

    failures = report.of(Outcome.FAILED)
    for result in failures:
        mark, style = MARKS[Outcome.FAILED]
        console.print()
        console.print(Text(f"{mark} {result.label}", style=style))
        detail = (
            str(result.error)
            if isinstance(result.error, CommandError)
            else f"{result.error}"
        )
        for line in detail.splitlines():
            console.print(f"  {line}", style=DETAIL, highlight=False, soft_wrap=True)

    if report.interrupted:
        console.print("\ninterrupted; nothing further was started.", style=CANCELLED)


def render_init_plan(console: Console, plan: InitPlan) -> None:
    for directory in plan.directories:
        console.print(
            f"mkdir -p {directory}", style=DETAIL, highlight=False, soft_wrap=True
        )
    if plan.write_config:
        console.print(
            f"write {plan.config_file}", style=DETAIL, highlight=False, soft_wrap=True
        )


def render_clean_plan(console: Console, plan: CleanPlan, *, dry_run: bool) -> None:
    verb = "Would empty" if dry_run else "Emptied"
    console.print(f"{verb} {plan.root}", style=OK, soft_wrap=True)
    if plan.projects:
        console.print(
            f"  including the object stores of {', '.join(plan.projects)}",
            style=DETAIL,
            soft_wrap=True,
        )
    if not dry_run:
        console.print(
            f"  the directory itself is left; remove it with `rmdir {plan.root}`",
            style=DETAIL,
            soft_wrap=True,
        )
