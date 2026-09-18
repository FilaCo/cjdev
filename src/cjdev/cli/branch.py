from pathlib import Path

from typer import Argument, Exit, Option, Typer

from cjdev.application.new_branch_set import DEFAULT_CHECKOUT_JOBS
from cjdev.application.workspace import require_root

from ._console import DETAIL, OK, console, diagnostics
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin, from_error
from ._progress import LIVE_AFTER, ConsoleProgress
from ._render import branch_set_payload, render_branch_set

cli = Typer(
    cls=CjdevGroup,
    name="branch",
    help="Branch sets: one branch name across every project.",
)


@cli.command(cls=CjdevCommand)
def new(
    ctx: CjdevContext,
    name: str = Argument(..., help="The branch, and the branch set it names."),
    path: Path | None = Argument(None, help="The workspace. Defaults to the cwd."),
    as_json: bool = Option(False, "--json", help="Print the report as JSON."),
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Create a branch set: one checkout per project, all on NAME."""
    out = begin("branch new", as_json=as_json)
    # A walk up from wherever the caller is standing: being inside another
    # branch set is a normal place to start one from.
    root = require_root((path or Path.cwd()).resolve())

    # The fan-out is not slowed for -v: the transcript is buffered per unit
    # and rendered in manifest order by `render_branch_set` afterwards.
    jobs = DEFAULT_CHECKOUT_JOBS
    progress = ConsoleProgress(
        out.display,
        fallback=None if dry_run else diagnostics,
        delay=LIVE_AFTER,
        # The table below is the report; the display only stands in for it
        # while the work runs, so it goes when the work does.
        transient=True,
    )
    ctx.obj.emit = progress.emit
    ctx.obj.report_step = progress.step
    if not dry_run:
        ctx.obj.journal(root, ["branch", "new", name])
    use_case = ctx.obj.new_branch_set(dry_run=dry_run, verbose=verbose, start=root)

    # Kept apart only because the display cannot be built until it knows
    # which projects it is tracking; there is nothing to ask in between.
    plan = use_case.plan(root, name, jobs=jobs, observer=progress.transcript)
    progress.track(
        [enrolment.project for enrolment in plan.to_enrol],
        title=f"Checking out {name}",
        # The estimate divides by what apply will use; a dry run is sequential
        # by its own rule - nothing to overlap.
        jobs=1 if dry_run else jobs,
    )

    with progress:
        report = use_case.apply(
            plan,
            jobs=jobs,
            dry_run=dry_run,
            observer=progress,
            transcript=progress.transcript,
        )

    if as_json:
        out.document(
            branch_set_payload(report),
            ok=report.ok,
            errors=[
                from_error(row.error, subject=row.project)
                for row in report.failures
                if row.error is not None
            ],
        )
    else:
        render_branch_set(console, report, lines=progress.lines)
        if dry_run:
            # Nothing happened, so nothing may read as if it had.
            console.print(
                f"\nDry run: {root} was not touched.", style=DETAIL, soft_wrap=True
            )
        elif report.ok:
            # The point of the command is the directory to cd into.
            console.print(
                f"\ncd {plan.directory}", style=OK, soft_wrap=True, highlight=False
            )
        else:
            console.print(f"\n{progress.summary()}", style=DETAIL, highlight=False)

    if not dry_run and not report.ok:
        raise Exit(1)
