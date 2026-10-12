from pathlib import Path

from typer import Exit, Option, Typer

from cjdev.application.runner import DEFAULT_NETWORK_JOBS
from cjdev.application.workspace import (
    enrolled_projects,
    require_branch_set,
    require_root,
)
from cjdev.domain.layout import WorkspaceLayout

from ._console import DETAIL, console, diagnostics
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin
from ._progress import LIVE_AFTER, ConsoleProgress
from ._render import render_rows, sync_rows

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def sync(
    ctx: CjdevContext,
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Bring the branch set you are standing in up to date with upstream.

    Fetches upstream, then fast-forwards every project whose branch has no
    commits of its own. A branch that has diverged is reported with the
    rebase that would fix it, never rebased.
    """
    begin("sync")
    cwd = Path.cwd().resolve()
    root = require_root(cwd)
    branch_set = require_branch_set(root, cwd)

    progress = ConsoleProgress(
        console,
        fallback=None if dry_run else diagnostics,
        delay=LIVE_AFTER,
        transient=True,
    )
    ctx.obj.emit = progress.emit
    ctx.obj.report_step = progress.step
    if not dry_run:
        ctx.obj.journal(root, ["sync"])
    use_case = ctx.obj.sync_branch_set(dry_run=dry_run, verbose=verbose, start=root)

    # The fetch is the wait, so it is what the display tracks; the
    # fast-forwards after it are local and quick.
    progress.track(
        enrolled_projects(WorkspaceLayout(root), ctx.obj.manifest(root), branch_set),
        title=f"Fetching upstream for {branch_set}",
        jobs=DEFAULT_NETWORK_JOBS,
    )
    with progress:
        plan = use_case.plan(root, branch_set, observer=progress)
    report = use_case.apply(plan, dry_run=dry_run, observer=progress.transcript)

    render_rows(
        console,
        sync_rows(report),
        interrupted=report.interrupted,
        lines=progress.lines,
    )
    if dry_run:
        console.print("\nDry run: nothing was fetched or moved.", style=DETAIL)
    if not report.ok:
        raise Exit(1)
