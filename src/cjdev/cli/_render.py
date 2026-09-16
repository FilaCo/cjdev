"""Turning a report into terminal output, and into the document `--json` prints.

Both renderings of one report live together on purpose: a field added to the
report has exactly two places to appear, and they are on the same screen. What
they may not share is a shape - the table hides what a reader would skim past,
and the payload hides nothing.
"""

from collections.abc import Callable
from typing import TypeVar

from rich.console import Console
from rich.table import Table
from rich.text import Text

from cjdev.application.new_branch_set import Action, BranchSetReport, Enrolled
from cjdev.application.runner import Outcome, RunReport
from cjdev.domain.state import BranchSet, Checkout, Store, WorkspaceStatus

from ._console import CANCELLED, DETAIL, MARKS, WAITING

T = TypeVar("T")

SHORT_SHA = 7
"""A table read many times a day cannot spend forty columns on a hash.
`--json` carries the full one."""

OUTCOMES: dict[Action, str] = {
    Action.CREATE: "created",
    Action.ADOPT: "adopted",
    Action.PRESENT: "present",
}
"""What became of one project, in one word. One mapping for the table and the
document alike, or the two of them drift apart on the next `Action`."""


def render_report(
    console: Console, report: RunReport[T], *, lines: Callable[[str], tuple[str, ...]]
) -> None:
    """What the command itself printed, then each unit, then each failure.

    `lines` supplies what was captured. It is rendered here, after the run,
    rather than as it happened: under a fan-out the order it happened in is the
    scheduler's, and the transcript is not allowed to be.
    """
    _detail(console, lines(""))

    for result in report.results:
        captured = lines(result.label)
        if not captured:
            continue
        console.print(result.label)
        _detail(console, captured, indent="  ")

    for result in report.of(Outcome.FAILED):
        mark, style = MARKS[Outcome.FAILED]
        console.print()
        console.print(Text(f"{mark} {result.label}", style=style))
        _detail(console, str(result.error).splitlines(), indent="  ")

    if report.interrupted:
        console.print("\ninterrupted; nothing further was started.", style=CANCELLED)


def render_branch_set(
    console: Console,
    report: BranchSetReport,
    *,
    lines: Callable[[str], tuple[str, ...]],
) -> None:
    """The set as one row per project, then whatever the run had to say.

    Paths are relative to the workspace root: they are there to be typed.
    """
    _detail(console, lines(""))

    root = report.plan.directory.parent
    table = Table.grid(padding=(0, 2))
    table.add_column(width=1)
    table.add_column()
    table.add_column()
    table.add_column(style=DETAIL)
    for row in report.rows:
        mark, style = MARKS[row.outcome]
        table.add_row(
            Text(mark, style=style),
            row.project,
            str(row.worktree.relative_to(root)),
            # Only against a `✓`: "created" next to a failure would be a lie.
            OUTCOMES[row.action] if row.outcome is Outcome.DONE else "",
        )
    console.print(table)

    for row in report.rows:
        captured = lines(row.project)
        if not captured:
            continue
        console.print(row.project)
        _detail(console, captured, indent="  ")

    for row in report.failures:
        mark, style = MARKS[Outcome.FAILED]
        console.print()
        console.print(Text(f"{mark} {row.project}", style=style))
        _detail(console, str(row.error).splitlines(), indent="  ")

    if report.interrupted:
        console.print("\ninterrupted; nothing further was started.", style=CANCELLED)


def branch_set_payload(report: BranchSetReport) -> dict[str, object]:
    """The same report, for something that is not a person. The outcomes are
    one field rather than a flag each."""
    return {
        "branch": report.plan.branch,
        "directory": str(report.plan.directory),
        "projects": [
            {
                "name": row.project,
                "path": str(row.worktree),
                "outcome": _outcome_of(row),
                "error": None if row.error is None else str(row.error),
            }
            for row in report.rows
        ],
    }


def _outcome_of(row: Enrolled) -> str:
    if row.outcome is not Outcome.DONE:
        return row.outcome.name.lower()
    return OUTCOMES[row.action]


def render_status(console: Console, status: WorkspaceStatus) -> None:
    console.print(f"Workspace  {status.root}", soft_wrap=True, highlight=False)

    if not status.branch_sets:
        console.print(
            "No branch sets yet - create one with `cjdev branch new <name>`.",
            style=DETAIL,
        )
    held = tuple(store.project for store in status.stores if store.provisioned)
    for branch_set in status.branch_sets:
        console.print()
        # A mark rather than a colour: the active branch set has to be
        # findable in a pipe and in a CI log too.
        mark = "*" if branch_set.name == status.active else " "
        console.print(f"{mark} {branch_set.name}")
        console.print(_checkouts(branch_set, held))

    _render_stores(console, status)


def status_payload(status: WorkspaceStatus) -> dict[str, object]:
    """The same report, for something that is not a person.

    Built by hand rather than from `asdict`, because the field names are a
    contract with whatever parses this and renaming a dataclass attribute must
    not silently break it. Counts appear whatever they are - the table hides a
    zero to stay skimmable, and a script has no such problem.
    """
    held = {store.project for store in status.stores if store.provisioned}
    return {
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
                "not_checked_out": list(_absent(branch_set, tuple(held))),
            }
            for branch_set in status.branch_sets
        ],
    }


def _detail(
    console: Console, lines: tuple[str, ...] | list[str], indent: str = ""
) -> None:
    # soft_wrap so a long path is left to the terminal instead of being broken
    # mid-word by rich's own word wrapping.
    for line in lines:
        console.print(f"{indent}{line}", style=DETAIL, highlight=False, soft_wrap=True)


def _absent(branch_set: BranchSet, held: tuple[str, ...]) -> tuple[str, ...]:
    """Projects the workspace holds that this branch set has no worktree for.

    Worth naming rather than leaving as a gap in the table: a project with no
    worktree here is not broken, it is simply not enrolled yet, and the two
    read identically when the row is just missing.
    """
    present = {checkout.project for checkout in branch_set.checkouts}
    return tuple(name for name in held if name not in present)


def _checkouts(branch_set: BranchSet, held: tuple[str, ...]) -> Table:
    rows: list[tuple[str | Text, str | Text, str, Text]] = [
        (
            checkout.project,
            checkout.branch or Text("detached", style=DETAIL),
            checkout.head[:SHORT_SHA],
            _attention(checkout),
        )
        for checkout in branch_set.checkouts
    ] + [
        (
            Text(project, style=DETAIL),
            Text("not checked out here", style=DETAIL),
            "",
            Text(""),
        )
        for project in _absent(branch_set, held)
    ]

    # A column rich would pad every row out to, for nothing: a branch set with
    # nothing to report would trail whitespace on every line of the report.
    noted = any(row[3].plain for row in rows)
    table = Table.grid(padding=(0, 2))
    table.add_column(width=2)
    table.add_column()
    table.add_column()
    table.add_column(style=DETAIL)
    if noted:
        table.add_column()
    for row in rows:
        table.add_row("", *(row if noted else row[:3]))
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
            f"\n  {waiting} not in this workspace - `cjdev init` adds it.",
            style=DETAIL,
            soft_wrap=True,
            highlight=False,
        )

    for store in status.stores:
        if store.error is None:
            continue
        mark, style = MARKS[Outcome.FAILED]
        console.print()
        console.print(Text(f"{mark} {store.project}", style=style))
        _detail(console, store.error.splitlines(), indent="  ")


def _store_mark(store: Store) -> tuple[str, str]:
    if store.error is not None:
        return MARKS[Outcome.FAILED]
    return MARKS[Outcome.DONE] if store.provisioned else WAITING
