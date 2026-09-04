from typer import Typer

from cjdev.errors import NotImplementedYetError

from ._context import CjdevCommand, CjdevContext, CjdevGroup

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def status(ctx: CjdevContext) -> None:
    """Show cjdev environment status."""
    _ = ctx
    raise NotImplementedYetError("cjdev status", "M1")
