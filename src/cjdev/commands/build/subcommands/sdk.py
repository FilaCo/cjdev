from typer import Typer, Context

cli = Typer()


@cli.command("sdk")
def build_sdk(ctx: Context):
    """Build all Cangjie's projects."""
    pass
