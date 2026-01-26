from pathlib import Path
from typing import Annotated, Any, Dict, Optional

import questionary
from pydantic_core import Url
from questionary import Choice
from rich import print
from tomlkit import dumps
from typer import Context, Option, Typer

from cjdev.commands.context import (
    CjDevContext,
    ContainerConfig,
    ProjectConfig,
    ProjectsConfig,
)

cli = Typer()


@cli.command()
def init(ctx: Context):
    """Init cjdev environment."""
    cjdev_ctx = ctx.ensure_object(CjDevContext)
    _questionnaire(cjdev_ctx)


def _default_project_config(name: str) -> Dict[str, Any]:
    return {
        "path": Path(name),
        "origin_url": Url(f"https://gitcode.com/Cangjie/{name}.git"),
        "upstream_url": Url(f"https://gitcode.com/Cangjie/{name}.git"),
        "default_branch": "dev",
    }


def _projects_questionnaire(
    prev_cfg: Optional[ProjectsConfig] = None,
) -> ProjectsConfig:
    placeholders = {p: _default_project_config(p) for p in ProjectsConfig.model_fields}
    prechecked = ["cangjie_compiler", "cangjie_runtime"]
    if prev_cfg:
        projects_dump = prev_cfg.model_dump(exclude_none=True)
        placeholders.update(projects_dump)
        prechecked = projects_dump.keys() if len(projects_dump) > 0 else prechecked

    chosen = questionary.checkbox(
        "Select projects to setup:",
        choices=list(
            map(
                lambda p: Choice(p, checked=p in prechecked),
                ProjectsConfig.model_fields,
            )
        ),
    ).ask()

    projects_cfg = {}
    for p in chosen:
        print(f"[bold blue]{p}[/bold blue] settings:")
        projects_cfg[p] = questionary.prompt(
            [
                {
                    "type": "text",
                    "name": "path",
                    "message": "Project path:",
                    "default": placeholders[p]["path"].as_posix(),
                },
                {
                    "type": "text",
                    "name": "origin_url",
                    "message": "Project origin URL:",
                    "default": f"{placeholders[p]['origin_url']}",
                },
                {
                    "type": "text",
                    "name": "upstream_url",
                    "message": "Project upstream URL:",
                    "default": f"{placeholders[p]['upstream_url']}",
                },
                {
                    "type": "text",
                    "name": "default_branch",
                    "message": "Project default branch:",
                    "default": placeholders[p]["default_branch"],
                },
            ]
        )

    return ProjectsConfig.model_validate(projects_cfg)


def _container_questionnaire(prev_cfg: Optional[ContainerConfig] = None):
    questions = [
        {
            "type": "confirm",
            "name": "use_container",
            "message": "Do you want to use a docker container for building?",
            "default": False,
        },
        {
            "type": "text",
            "name": "container_name",
            "message": "Container name:",
            "default": "cjdev",
            "when": lambda answers: answers["use_container"],
        },
        {
            "type": "text",
            "name": "host_workdir",
            "message": "Host working directory:",
            "default": Path.cwd().as_posix(),
            "when": lambda answers: answers["use_container"],
        },
        {
            "type": "text",
            "name": "container_workdir",
            "message": "Container working directory:",
            "when": lambda answers: answers["use_container"],
        },
    ]

    container_cfg = questionary.prompt(questions)

    return ContainerConfig.model_validate(container_cfg)


def _questionnaire(ctx: CjDevContext):
    config = ctx.config
    config_path = ctx.config_path
    config_exists = config_path.exists()
    override_config = questionary.confirm(
        f"I see an existing config at {config_path.as_posix()}. Are you sure you want to override it?",
        default=False,
    ).ask()
    if not override_config:
        print("Got it, exiting...")
        return
    config.container = _container_questionnaire(
        config.container if config_exists else None
    )
    config.projects = _projects_questionnaire(
        config.projects if config_exists else None
    )
    config_path.write_text(dumps(config.model_dump()))
