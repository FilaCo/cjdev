from pathlib import Path

from typer import Argument, Option, Typer

from ._console import console
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin
from ._render import config_payload, render_config_show

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
