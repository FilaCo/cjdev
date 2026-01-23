from typing import Annotated

import questionary
from rich import print
from typer import Option, Typer

cli = Typer()


@cli.command()
def init():
    """Init cjdev environment."""
    pass
