from typing import Annotated

import questionary
from rich import print
from typer import Context, Option, Typer

from cjdev.commands.context import ProjectsConfig

cli = Typer()


@cli.command()
def init(ctx: Context):
    """Init cjdev environment."""
    config_path = ctx.obj.config_path
    questionary.checkbox(
        "Select projects to setup:", choices=ProjectsConfig.model_fields
    ).ask()
