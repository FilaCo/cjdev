from typer import Typer

from cjdev.utils.version import VERSION_TYPE_DEF

cli = Typer()


@cli.command()
def build(version: VERSION_TYPE_DEF = False):
    """Build Cangjie's projects."""
    pass
