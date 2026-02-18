from typer import Typer, Context

cli = Typer()


@cli.command("rt")
@cli.command("runtime", hidden=True)
def build_runtime(ctx: Context):
    """Build runtime."""
    pass
