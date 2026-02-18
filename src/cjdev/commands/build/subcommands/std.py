from typer import Typer, Context

cli = Typer()


@cli.command("std")
@cli.command("stdlib", hidden=True)
def build_std(ctx: Context):
    """Build standard library."""
    pass
