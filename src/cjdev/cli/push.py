from pathlib import Path

from typer import Exit, Option, Typer

from cjdev.application.runner import DEFAULT_NETWORK_JOBS
from cjdev.application.workspace import require_branch_set, require_root

from ._console import DETAIL, console, diagnostics
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin
from ._progress import LIVE_AFTER, ConsoleProgress
from ._render import push_rows, render_rows

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def push(
    ctx: CjdevContext,
    force_with_lease: bool = Option(
        False,
        "--force-with-lease",
        help="Replace origin's copy of a rewritten branch, if it is still what "
        "this workspace last saw.",
    ),
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Push the branch set you are standing in to your fork.

    Every project ahead of origin is pushed there, with tracking set on the
    first push, and the report says where to open each PR. Never pushes to
    upstream.
    """
    begin("push")
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
        ctx.obj.journal(
            root, ["push", *(["--force-with-lease"] if force_with_lease else [])]
        )
    use_case = ctx.obj.push_branch_set(dry_run=dry_run, verbose=verbose, start=root)

    plan = use_case.plan(
        root, branch_set, force=force_with_lease, observer=progress.transcript
    )
    progress.track(
        [step.project for step in plan.to_push],
        title=f"Pushing {branch_set}",
        jobs=1 if dry_run else DEFAULT_NETWORK_JOBS,
    )
    with progress:
        report = use_case.apply(plan, dry_run=dry_run, observer=progress)

    render_rows(
        console,
        push_rows(report),
        interrupted=report.interrupted,
        lines=progress.lines,
    )
    if dry_run:
        console.print("\nDry run: nothing was pushed.", style=DETAIL)
    if not report.ok:
        raise Exit(1)
