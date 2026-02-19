from typing import Annotated

from dependency_injector.wiring import inject
from typer import Argument, Typer

from cjdev.command.domain.git.aggregate_root.repos import Repos

cli = Typer()


@cli.command()
# @inject
def upload():
    """Creates pull requests to upstreams."""
    pass
