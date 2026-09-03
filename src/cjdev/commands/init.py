from typer import Typer

cli = Typer()


@cli.command()
def init() -> None:
    """Create a cjdev workspace in the current directory."""
