from typing import Annotated

import questionary
from questionary import Choice
from rich import print
from typer import Context, Option, Typer

from cjdev.commands.context import CjDevContext, ProjectsConfig

cli = Typer()


def quesionnaire(ctx: CjDevContext):
    config_path = ctx.config_path
    checked_projects = ["cangjie_compiler", "cangjie_runtime"]
    return [
        {
            "type": "checkbox",
            "name": "projects",
            "message": "Select projects to setup:",
            "choices": list(
                map(
                    lambda p: Choice(p, checked=p in checked_projects),
                    ProjectsConfig.model_fields,
                )
            ),
        },
        {
            "type": "confirm",
            "name": "use_container",
            "message": "Do you want to use a docker container for building?",
            "default": False,
        },
    ]


@cli.command()
def init(ctx: Context):
    """Init cjdev environment."""
    cjdev_ctx = ctx.ensure_object(CjDevContext)
    config_path = cjdev_ctx.config_path
    config_exists = config_path.exists()
    config = cjdev_ctx.config

    should_override = questionary.confirm("Override existing configuration?").skip_if(
        config_exists, default=False
    )
