from typer import Typer

cli = Typer()


@cli.command()
def dc():
    """Execute a command in the container"""
    pass
