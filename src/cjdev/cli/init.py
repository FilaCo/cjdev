from typer import Typer

from ._context import CjdevCommand, CjdevContext, CjdevGroup

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def init(ctx: CjdevContext) -> None:
    """Create a cjdev workspace in the current directory."""
    ctx.obj.initialize_workspace.perform()
