from typing import Annotated

from dependency_injector.wiring import inject
from typer import Argument, Typer

from cjdev.command.domain.git.aggregate_root.repos import Repos

cli = Typer()


@cli.command()
def switch(
    branch: Annotated[
        str,
        Argument(
            help="Target branch.",
        ),
    ],
):
    """Switch all projects to the specified branch."""
    pass
