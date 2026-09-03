from typer import Typer

cli = Typer()


@cli.command()
def status() -> None:
    """Show cjdev environment status."""
