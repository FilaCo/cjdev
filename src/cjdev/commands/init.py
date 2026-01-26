from typing import Annotated

import questionary
from questionary import Choice
from rich import print
from typer import Context, Option, Typer

from cjdev.commands.context import CjDevContext, ProjectsConfig

cli = Typer()


@cli.command()
def init(ctx: Context):
    """Init cjdev environment."""
    cjdev_ctx = ctx.ensure_object(CjDevContext)
    _projects_questionnaire(cjdev_ctx)
    # config_path = cjdev_ctx.config_path
    # config_exists = config_path.exists()
    # config = cjdev_ctx.config


def _projects_questionnaire(ctx: CjDevContext):
    prechecked = ["cangjie_compiler", "cangjie_runtime"]
    all_projects = list(filter(lambda p: p != "branch", ProjectsConfig.model_fields))
    chosen = questionary.checkbox(
        "Select projects to setup:",
        choices=list(map(lambda p: Choice(p, checked=p in prechecked), all_projects)),
    ).ask()


def _container_questionnaire(ctx: CjDevContext):
    config_path = ctx.config_path
    return [
        {
            "type": "checkbox",
            "name": "projects",
            "message": "Select projects to setup:",
            "choices": list(),
        },
        {
            "type": "confirm",
            "name": "use_container",
            "message": "Do you want to use a docker container for building?",
            "default": False,
        },
    ]


def _questionnaire(ctx: CjDevContext):
    pass
