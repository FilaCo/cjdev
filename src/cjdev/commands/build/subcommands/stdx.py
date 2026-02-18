from typer import Typer, Context

cli = Typer()


@cli.command("stdx")
def build_stdx(ctx: Context):
    """Build standard library extensions."""
    pass
