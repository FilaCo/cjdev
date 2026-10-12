from pathlib import Path

from typer import Argument, Option, Typer

from cjdev.application.workspace import require_root

from ._console import diagnostics
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin
from .branch import check_out, finish, progress_for

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def start(
    ctx: CjdevContext,
    subject: str = Argument(
        ..., help="The issue's URL; with --no-issue, the branch set's name."
    ),
    name: str | None = Option(
        None, "--name", help="The branch set, instead of issue-<n>-<title>."
    ),
    no_issue: bool = Option(
        False, "--no-issue", help="Start without an issue; attach one later."
    ),
    home: str | None = Option(
        None,
        "--home",
        help="With --no-issue: the project the issue will live in. "
        "Defaults to forge.issue_home in .cjdev/config.toml.",
    ),
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Start a task: a branch set for an issue, cut from fresh upstream.

    Reads the issue from GitCode (token: GITCODE_TOKEN, else git's stored
    credential for gitcode.com), names the branch set issue-<n>-<title>,
    fetches upstream in every project and branches from its default branch.
    The issue is remembered for later commands. Run it inside the workspace.
    """
    out = begin("start")
    root = require_root(Path.cwd().resolve())
    progress = progress_for(out, dry_run=dry_run)
    ctx.obj.emit = progress.emit
    ctx.obj.report_step = progress.step
    if not dry_run:
        ctx.obj.journal(
            root,
            [
                "start",
                subject,
                *(["--no-issue"] if no_issue else []),
                *([f"--name={name}"] if name else []),
                *([f"--home={home}"] if home else []),
            ],
        )
    tasks = ctx.obj.tasks(dry_run=dry_run, verbose=verbose, start=root)

    started = tasks.start(subject, no_issue=no_issue, name=name, home=home)
    if not dry_run:
        diagnostics.print("Fetching upstream...", highlight=False)
    tasks.fetch(root, observer=progress.transcript)
    report = check_out(
        ctx, root, started.branch_set, progress, dry_run=dry_run, verbose=verbose
    )
    if report.ok:
        tasks.remember(root, started.branch_set, started.task)
    finish(out, root, report, progress, as_json=False, dry_run=dry_run)
