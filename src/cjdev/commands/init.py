from typing import Annotated

import questionary
from rich import print
from typer import Context, Option, Typer

cli = Typer()


@cli.command()
def init(ctx: Context):
    """Init cjdev environment."""
    print("Initializing cjdev environment...")
    print(ctx.obj.container.use_container)
    pass
