from pathlib import Path

from typer import Argument, Exit, Option, Typer

from cjdev.application.runner import DEFAULT_NETWORK_JOBS, Outcome
from cjdev.infra.config import load_bundled_manifest

from ._console import DETAIL, OK, console, diagnostics
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin, from_error
from ._progress import ConsoleProgress
from ._render import init_payload, render_report

cli = Typer(cls=CjdevGroup)


def complete_project(incomplete: str) -> list[str]:
    """Project names for the shell, from the shipped manifest.

    Completion runs in its own process with no context, exactly as
    `complete_unit` does: a workspace that overrides the project set still
    completes to the shipped names.
    """
    return [
        project.name
        for project in load_bundled_manifest().projects
        if project.name.startswith(incomplete)
    ]


@cli.command(cls=CjdevCommand)
def init(
    ctx: CjdevContext,
    path: Path = Argument(Path(), help="Where to create the workspace."),
    projects: list[str] = Option(
        None,
        "-p",
        "--project",
        help="A project this workspace holds. Repeat per project; "
        "naming any answers the question instead of asking it.",
        autocompletion=complete_project,
    ),
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
    as_json: bool = Option(
        False, "--json", help="Print the result as JSON. Implies --defaults."
    ),
) -> None:
    """Create a cjdev workspace."""
    out = begin("init", as_json=as_json)
    root = path.resolve()
    # No per-unit fallback lines under --dry-run: nothing is happening, so
    # there is no progress to keep a pipe informed about.
    progress = ConsoleProgress(out.display, fallback=None if dry_run else diagnostics)
    ctx.obj.emit = progress.emit
    ctx.obj.report_step = progress.step
    if not dry_run:
        ctx.obj.journal(root, ["init", str(path)])
    use_case = ctx.obj.init_workspace(
        dry_run=dry_run,
        verbose=verbose,
        # A wizard drawn over the document would corrupt it, and stdout is
        # already spoken for. `--yes` is untouched by this: it is consent,
        # and `--json` supplies answers, not permission.
        defaults=defaults or as_json,
        assume_yes=assume_yes,
    )

    # `-p` is an answer to the question the wizard asks, so it goes in here
    # rather than into `defaults`: naming the project set on a terminal still
    # leaves the deletion it may imply to be confirmed out loud.
    named = tuple(projects or ())
    plan = use_case.agree(use_case.plan(root), root, selection=named or None)
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

    if as_json:
        if dry_run:
            # A dry run's whole output is the command list UX-1 promises, and
            # dropping it because a caller asked for JSON would be answering a
            # different question. It goes to stderr rather than into the
            # document: the document says what would change, not how. A real
            # run's transcript is thousands of lines and goes to the log file
            # instead (PAR-11).
            render_report(out.display, report, lines=progress.lines)
        out.document(
            init_payload(root, plan, report, dry_run=dry_run),
            ok=report.ok,
            errors=[
                from_error(result.error, subject=result.label)
                for result in report.of(Outcome.FAILED)
                if result.error is not None
            ],
        )
        if not report.ok:
            raise Exit(1)
        return

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
