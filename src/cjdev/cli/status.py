from pathlib import Path

from typer import Argument, Exit, Option, Typer

from cjdev.application.report_status import DEFAULT_QUERY_JOBS
from cjdev.application.workspace import require_root

from ._console import DETAIL, console, diagnostics
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._render import render_status, render_status_json

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def status(
    ctx: CjdevContext,
    path: Path | None = Argument(None, help="The workspace. Defaults to the cwd."),
    jobs: int = Option(
        DEFAULT_QUERY_JOBS, "-j", "--jobs", help="Projects to query at once."
    ),
    as_json: bool = Option(False, "--json", help="Print the report as JSON."),
    verbose: bool = Option(False, "-v", "--verbose", help="Echo every command."),
) -> None:
    """Show what this workspace holds: branch sets, projects and their git state."""
    # Walking up from a named path, unlike `clean`, which insists on being
    # handed the root itself. That asymmetry is deliberate: `clean` empties
    # what it finds, and reading is not worth the same caution.
    root = require_root((path or Path.cwd()).resolve())

    # -v echoes each command as it runs, and under a fan-out the order it
    # echoes in would belong to the scheduler. -j1 is the supported way to get
    # a readable transcript, so asking for one implies it.
    if verbose:
        jobs = 1
    ctx.obj.emit = lambda line: diagnostics.print(
        line, style=DETAIL, highlight=False, soft_wrap=True
    )

    # The cwd is resolved for the same reason the root is: git reports
    # worktree paths physically, so one reached through a symlink would match
    # no branch set and `status` would quietly say you are standing outside
    # all of them.
    report = ctx.obj.report_status(verbose=verbose).perform(
        root, cwd=Path.cwd().resolve(), jobs=jobs
    )

    if as_json:
        # markup and highlighting off, soft_wrap on: rich must not colour,
        # rewrap or reinterpret a document something else is about to parse.
        console.print(
            render_status_json(report), markup=False, highlight=False, soft_wrap=True
        )
    else:
        render_status(console, report)

    # A report that could not read every project is still worth printing, but
    # it is not a success: a prompt or a script that treats it as one would be
    # acting on a workspace it only partly saw.
    if any(store.error is not None for store in report.stores):
        raise Exit(1)
