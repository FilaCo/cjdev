from pathlib import Path

from typer import Argument, Exit, Option, Typer

from cjdev.application.runner import DEFAULT_NETWORK_JOBS

from ._console import DETAIL, OK, console, diagnostics
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._progress import ConsoleProgress
from ._render import render_report

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
    assume_yes: bool = Option(
        False, "-y", "--yes", help="Consent to deleting the projects being dropped."
    ),
) -> None:
    """Create a cjdev workspace."""
    root = path.resolve()
    # No per-unit fallback lines under --dry-run: nothing is happening, so
    # there is no progress to keep a pipe informed about.
    progress = ConsoleProgress(console, fallback=None if dry_run else diagnostics)
    ctx.obj.emit = progress.emit
    ctx.obj.report_step = progress.step
    if not dry_run:
        ctx.obj.journal(root, ["init", str(path)])
    use_case = ctx.obj.init_workspace(
        dry_run=dry_run, verbose=verbose, defaults=defaults, assume_yes=assume_yes
    )

    plan = use_case.agree(use_case.plan(root), root)
    labels = [p.name for p in plan.to_provision + plan.to_remove]
    progress.track(
        labels,
        title=f"Fetching {len(plan.to_provision)} project(s)"
        if plan.to_provision
        else "Updating the workspace",
        jobs=1 if dry_run else jobs,
    )

    with progress:
        report = use_case.apply(
            root, plan, jobs=jobs, dry_run=dry_run, observer=progress
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
