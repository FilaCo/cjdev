from typer import Typer

from cjdev.utils.version import VERSION_TYPE_DEF

cli = Typer()


@cli.command()
def test(version: VERSION_TYPE_DEF = False):
    """Test Cangjie's projects."""
    pass
