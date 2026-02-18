from typing import Annotated

from typer import Argument, Typer

cli = Typer()


@cli.command()
# @inject
def upload():
    """Creates pull requests to upstreams."""
    pass
