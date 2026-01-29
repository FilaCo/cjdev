from typer import Typer

from cjdev.utils.version import VERSION_TYPE_DEF

cli = Typer()


@cli.command()
def git(version: VERSION_TYPE_DEF = False):
    """Git utils for Cangjie's repositories management."""
    pass
