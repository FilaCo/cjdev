from pathlib import Path

from typer import Argument, Exit, Option, Typer

from cjdev.application.workspace import held_projects, require_root
from cjdev.domain.layout import WorkspaceLayout

from ._console import console, diagnostics
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin, problem
from ._progress import Transcript
from ._render import render_status, status_payload

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def status(
    ctx: CjdevContext,
    path: Path | None = Argument(None, help="The workspace. Defaults to the cwd."),
    as_json: bool = Option(False, "--json", help="Print the report as JSON."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Show what this workspace holds: branch sets, projects and their git state."""
    out = begin("status", as_json=as_json)
    # A walk up from wherever the caller is standing, the way git's own
    # commands work: being inside a worktree is the normal place to ask from,
    # and reading warrants none of the caution a removal would.
    root = require_root((path or Path.cwd()).resolve())

    # Buffered like every command's transcript: the fan-out is not slowed for
    # it, and the flush below prints it in manifest order.
    transcript = Transcript()
    ctx.obj.emit = transcript.emit

    # The labels come from the layout, not from the report: the flush has to
    # survive the run failing, when there is no report to name them.
    # Resolved before the use case is built, so an unreadable workspace config
    # fails here with the file named, before anything runs.
    manifest = ctx.obj.manifest(root)
    projects = list(held_projects(WorkspaceLayout(root), manifest))

    # The cwd is resolved for the same reason the root is: git reports
    # worktree paths physically, so one reached through a symlink would match
    # no branch set and `status` would quietly say you are standing outside
    # all of them.
    try:
        report = ctx.obj.report_status(verbose=verbose, start=root).perform(
            root,
            cwd=Path.cwd().resolve(),
            observer=transcript,
        )
    finally:
        # A Ctrl-C or a refusal skips everything after `perform`; the commands
        # that did run are still worth seeing. Ordered by the layout, which is
        # the same order the report's stores come in when there is a report.
        if verbose:
            transcript.flush(diagnostics, projects)

    # A report that could not read every project is still worth printing, but
    # it is not a success: a prompt or a script that treats it as one would be
    # acting on a workspace it only partly saw. The document says both at once -
    # everything that was read, and `ok: false` next to what was not.
    unreadable = [
        problem("project_unreadable", message, subject=store.project)
        for store in report.stores
        if (message := store.error) is not None
    ]

    if as_json:
        out.document(status_payload(report), ok=not unreadable, errors=unreadable)
    else:
        render_status(console, report)

    if unreadable:
        raise Exit(1)
