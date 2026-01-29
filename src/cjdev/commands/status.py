from typer import Typer

from cjdev.utils.version import VERSION_TYPE_DEF

cli = Typer()


@cli.command()
def status(version: VERSION_TYPE_DEF = False):
    """Show cjdev environment status."""
    pass
