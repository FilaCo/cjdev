from pathlib import Path

from typer import Argument, Exit, Option, Typer

from cjdev.application.workspace import require_root

from ._console import console
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin
from ._progress import Transcript
from ._render import config_payload, render_config_show, render_origin

cli = Typer(
    cls=CjdevGroup,
    name="config",
    help="The workspace's configuration.",
)


@cli.command(cls=CjdevCommand)
def show(
    ctx: CjdevContext,
    path: Path | None = Argument(None, help="The workspace. Defaults to the cwd."),
    as_json: bool = Option(False, "--json", help="Print the report as JSON."),
    verbose: bool = Option(
        False, "-v", "--verbose", help="Show which layer every value came from."
    ),
) -> None:
    """Show the effective configuration: the bundled manifest with this
    workspace's `.cjdev/config.toml` layered over it."""
    out = begin("config show", as_json=as_json)
    # A read: it walks up the way git's own commands do, and outside any
    # workspace it shows the bundled manifest alone (FR-9).
    start = (path or Path.cwd()).resolve()

    layered = ctx.obj.layered(start)
    environment = ctx.obj.environment(start)

    if as_json:
        # The layers are always in the payload; -v governs only the table.
        out.document(config_payload(layered, environment))
    else:
        render_config_show(console, layered, environment, verbose=verbose)


@cli.command(cls=CjdevCommand)
def origin(
    ctx: CjdevContext,
    owner: str | None = Argument(
        None,
        help="Whose forks origin points at; recorded as [forge] fork_owner. "
        "Defaults to the recorded one.",
    ),
    path: Path | None = Option(
        None, "--workspace", "-w", help="The workspace. Defaults to the cwd."
    ),
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Point origin at OWNER's forks.

    In every project that has no origin yet, derived from its upstream. An
    origin that points elsewhere is reported, never replaced.
    """
    begin("config origin")
    root = require_root((path or Path.cwd()).resolve())
    transcript = Transcript()
    ctx.obj.emit = transcript.emit
    if not dry_run:
        ctx.obj.journal(root, ["config", "origin", *([owner] if owner else [])])
    report = ctx.obj.wire_origin(dry_run=dry_run, verbose=verbose, start=root).perform(
        root, owner, observer=transcript
    )
    render_origin(console, report, lines=transcript.lines)
    if not report.ok:
        raise Exit(1)
