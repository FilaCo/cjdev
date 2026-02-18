from typing import Annotated

from typer import Option, Typer

cli = Typer()


@cli.command()
# @inject
def sync(
    sync_origin: Annotated[
        bool,
        Option("--sync-origin", help="Sync origin to upstream"),
    ],
):
    """Sync all projects to the upstream default branch."""
    pass
