from typing import Annotated

from typer import Argument, Typer

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
