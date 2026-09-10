import sys
from pathlib import Path

from typer import Argument, Exit, Option, Typer

from cjdev.application.runner import DEFAULT_NETWORK_JOBS
from cjdev.errors import InputRequiredError

from ._console import DETAIL, OK, console, diagnostics
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin
from ._progress import LIVE_AFTER, ConsoleProgress
from ._render import render_report

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def init(
    ctx: CjdevContext,
    path: Path = Argument(Path(), help="Where to create the workspace."),
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Echo every command."),
) -> None:
    """Create a cjdev workspace."""
    # Resets the reporting mode as much as it names the command: the mode is
    # module state, so an earlier `--json` invocation in the same process
    # would otherwise still be in force when this one failed.
    begin("init")
    root = path.resolve()

    # The wizard is the only way `init` learns which projects to fetch, so
    # with no terminal there is no answer to be had and no flag that supplies
    # one yet. Failing beats waiting on a stdin nobody is going to write to.
    if not dry_run and not sys.stdin.isatty():
        raise InputRequiredError(
            "cjdev init asks which projects this workspace holds, and there "
            "is no terminal to ask at.",
            remedy="run it from a terminal, or pass --dry-run for the plan",
        )

    # No per-unit fallback lines under --dry-run: nothing is happening, so
    # there is no progress to keep a pipe informed about.
    progress = ConsoleProgress(
        console,
        fallback=None if dry_run else diagnostics,
        # A workspace that already matches the answers finishes at once, and
        # only a run with fetching to do is worth drawing for.
        delay=LIVE_AFTER,
    )
    ctx.obj.emit = progress.emit
    ctx.obj.report_step = progress.step
    if not dry_run:
        ctx.obj.journal(root, ["init", str(path)])
    use_case = ctx.obj.init_workspace(dry_run=dry_run, verbose=verbose)

    plan = use_case.agree(use_case.plan(root), root)
    labels = [p.name for p in plan.to_provision + plan.to_remove]
    progress.track(
        labels,
        title=f"Fetching {len(plan.to_provision)} project(s)"
        if plan.to_provision
        else "Updating the workspace",
        jobs=1 if dry_run else DEFAULT_NETWORK_JOBS,
    )

    with progress:
        report = use_case.apply(
            root,
            plan,
            jobs=DEFAULT_NETWORK_JOBS,
            dry_run=dry_run,
            observer=progress,
        )

    render_report(console, report, lines=progress.lines)

    if dry_run:
        # Nothing happened, so nothing may read as if it had: the plan above
        # is the whole output, and "ready" would be a lie about a workspace
        # that does not exist.
        console.print(
            f"\nDry run: {root} was not touched.", style=DETAIL, soft_wrap=True
        )
    elif not report.ok:
        console.print(f"\n{progress.summary()}", style=DETAIL, highlight=False)
        raise Exit(1)
    elif plan.is_noop:
        # Re-running on a workspace that already matches the answers is the
        # normal way to check one, so it says so rather than claiming to have
        # done work it skipped.
        console.print(
            f"Workspace at {root} is already up to date.",
            style=DETAIL,
            highlight=False,
            soft_wrap=True,
        )
    else:
        if labels:
            console.print(f"\n{progress.summary()}", style=DETAIL, highlight=False)
        console.print(f"Workspace ready at {root}", style=OK, soft_wrap=True)
