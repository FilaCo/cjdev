from typing import Annotated

from dependency_injector.wiring import inject
from typer import Option, Typer

from cjdev.command.domain.git.aggregate_root.repos import Repos

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
