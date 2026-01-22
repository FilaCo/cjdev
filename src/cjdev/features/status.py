from typer import Typer

cli = Typer()


@cli.command()
def status():
    """Show cjdev environment status"""
    pass
