"""Turning a report into terminal output (UX-4, UX-8, PAR-4)."""

import json
from collections.abc import Callable
from typing import TypeVar

from rich.console import Console
from rich.table import Table
from rich.text import Text

from cjdev.application.clean_workspace import CleanPlan
from cjdev.application.init_workspace import InitPlan
from cjdev.application.runner import Outcome, RunReport
from cjdev.domain.state import BranchSet, Checkout, Store, WorkspaceStatus
from cjdev.errors import CommandError

from ._console import CANCELLED, DETAIL, MARKS, OK, WAITING

T = TypeVar("T")

SHORT_SHA = 7
"""BRANCH-4 asks for a short SHA, and a table read many times a day cannot
spend forty columns on a hash. `--json` carries the full one (UX-6)."""


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


def render_status(console: Console, status: WorkspaceStatus) -> None:
    console.print(f"Workspace  {status.root}", soft_wrap=True)

    if not status.branch_sets:
        console.print(
            "No branch sets yet - create one with `cjdev branch new <name>`.",
            style=DETAIL,
        )
    for branch_set in status.branch_sets:
        console.print()
        # A mark rather than a colour: the active branch set has to be
        # findable in a pipe and in a CI log too.
        mark = "*" if branch_set.name == status.active else " "
        console.print(f"{mark} {branch_set.name}")
        console.print(_checkouts(branch_set))

    _render_stores(console, status)


def render_status_json(status: WorkspaceStatus) -> str:
    """The same report, for something that is not a person (UX-6).

    Built by hand rather than from `asdict`, because the field names are a
    contract with whatever parses this and renaming a dataclass attribute must
    not silently break it. Counts appear whatever they are - the table hides a
    zero to stay skimmable, and a script has no such problem.
    """
    return json.dumps(
        {
            "root": str(status.root),
            "active_branch_set": status.active,
            "projects": [
                {
                    "name": store.project,
                    "provisioned": store.provisioned,
                    "error": store.error,
                }
                for store in status.stores
            ],
            "branch_sets": [
                {
                    "name": branch_set.name,
                    "directory": str(branch_set.directory),
                    "projects": [
                        {
                            "name": checkout.project,
                            "path": str(checkout.path),
                            "branch": checkout.branch,
                            "head": checkout.head,
                            "dirty": checkout.dirty,
                            "tracking": [
                                {
                                    "remote": tracking.remote,
                                    "ahead": tracking.ahead,
                                    "behind": tracking.behind,
                                }
                                for tracking in checkout.tracking
                            ],
                        }
                        for checkout in branch_set.checkouts
                    ],
                }
                for branch_set in status.branch_sets
            ],
        },
        indent=2,
    )


def _checkouts(branch_set: BranchSet) -> Table:
    attention = [_attention(checkout) for checkout in branch_set.checkouts]
    table = Table.grid(padding=(0, 2))
    table.add_column(width=2)
    table.add_column()
    table.add_column()
    table.add_column(style=DETAIL)
    # A column rich would pad every row out to, for nothing: a branch set with
    # nothing to report would trail whitespace on every line of the report.
    if any(attention):
        table.add_column()
    for checkout, note in zip(branch_set.checkouts, attention, strict=True):
        row = (
            "",
            checkout.project,
            checkout.branch or Text("detached", style=DETAIL),
            checkout.head[:SHORT_SHA],
        )
        table.add_row(*((*row, note) if any(attention) else row))
    return table


def _attention(checkout: Checkout) -> Text:
    """Only what the reader has to do something about.

    A remote in sync and a remote that has never heard of this branch both
    mean "nothing to do here", and six projects times two remotes of `0/0`
    would bury the one row that does need attention. The full counts are in
    `--json`.
    """
    parts = [Text("dirty", style=CANCELLED)] if checkout.dirty else []
    for tracking in checkout.tracking:
        drift = " ".join(
            f"{mark}{count}"
            for mark, count in (("↑", tracking.ahead), ("↓", tracking.behind))
            if count
        )
        if drift:
            parts.append(Text(f"{tracking.remote} {drift}", style=DETAIL))
    return Text("  ").join(parts)


def _render_stores(console: Console, status: WorkspaceStatus) -> None:
    """Which projects this workspace holds - the same marks a fan-out uses.

    Present, absent and unreadable in one aligned column rather than three
    sections, because the question being asked of them is one question, and
    because until a branch set exists this is the whole of the report.
    """
    console.print()
    console.print("Projects")
    # Printed rather than tabulated: the marks are one column wide, so the
    # rows line up on their own and a grid would only pad every name out to
    # the longest one.
    for store in status.stores:
        mark, style = _store_mark(store)
        console.print(Text(f"  {mark} ", style=style).append(store.project, style=""))

    if any(not store.provisioned for store in status.stores):
        waiting, _ = WAITING
        console.print(
            f"  {waiting} not in this workspace; add it by re-running `cjdev init`",
            style=DETAIL,
        )

    for store in status.stores:
        if store.error is None:
            continue
        mark, style = MARKS[Outcome.FAILED]
        console.print()
        console.print(Text(f"{mark} {store.project}", style=style))
        for line in store.error.splitlines():
            console.print(f"  {line}", style=DETAIL, highlight=False, soft_wrap=True)


def _store_mark(store: Store) -> tuple[str, str]:
    if store.error is not None:
        return MARKS[Outcome.FAILED]
    return MARKS[Outcome.DONE] if store.provisioned else WAITING
