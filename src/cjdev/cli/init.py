from pathlib import Path

from typer import Argument, Exit, Option, Typer

from cjdev.application.runner import DEFAULT_NETWORK_JOBS

from ._console import DETAIL, OK, console
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._progress import ConsoleProgress
from ._render import render_init_plan, render_report

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def init(
    ctx: CjdevContext,
    path: Path = Argument(Path(), help="Where to create the workspace."),
    jobs: int = Option(
        DEFAULT_NETWORK_JOBS, "-j", "--jobs", help="Projects to fetch at once."
    ),
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Echo every command."),
    defaults: bool = Option(
        False, "--defaults", help="Skip the wizard and take every default."
    ),
) -> None:
    """Create a cjdev workspace."""
    root = path.resolve()
    progress = ConsoleProgress(console)
    ctx.obj.emit = progress.emit
    use_case = ctx.obj.init_workspace(
        dry_run=dry_run, verbose=verbose, defaults=defaults
    )

    plan = use_case.plan(root)
    if dry_run:
        render_init_plan(console, plan)
    plan = use_case.agree(plan, root)
    progress.track([p.name for p in plan.to_provision + plan.to_remove])

    with progress:
        report = use_case.apply(
            root, plan, jobs=jobs, dry_run=dry_run, observer=progress
        )

    render_report(console, report, lines=progress.lines)
    if not report.results:
        console.print("Nothing to do.", style=DETAIL)
    elif report.ok:
        console.print(f"\nWorkspace ready at {root}", style=OK, soft_wrap=True)
    else:
        raise Exit(1)
