from typer import Typer

from ._context import CjdevCommand, CjdevContext, CjdevGroup

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def status(ctx: CjdevContext) -> None:
    """Show cjdev environment status."""
    ctx.obj.get_workspace_status.perform()
