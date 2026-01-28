from pathlib import Path
from typing import Any, Dict, Optional

import questionary
from pydantic import ValidationError
from pydantic_core import Url
from questionary import Choice
from rich import print
from tomlkit import dumps
from typer import Context, Option, Typer

from cjdev.commands.context import (
    CjDevContext,
    Config,
    ContainerConfig,
    ProjectsConfig,
)

cli = Typer()


@cli.command()
def init(ctx: Context):
    """Init cjdev environment."""
    cjdev_ctx = ctx.ensure_object(CjDevContext)
    _init(cjdev_ctx)


def _init(cjdev_ctx: CjDevContext):
    cfg_path = cjdev_ctx.config_path
    cfg = cjdev_ctx.config
    try:
        new_cfg = _questionnaire(cfg_path, cfg)
        new_cfg.save(cfg_path)
        cjdev_ctx.config = new_cfg
        print(f"Config saved successfully at {cfg_path.as_posix()}!")
    except ValidationError as e:
        print(f"Incorrect configuration provided: {e}")
        print("Changes won't be saved. Please, try again. Bye!")
    except KeyboardInterrupt:
        print("Cancelled by user")


def _questionnaire(cfg_path: Path, prev_cfg: Config) -> Config:
    cfg_exists = cfg_path.exists()
    override_config = (
        questionary.confirm(
            f"Existing configuration found at {cfg_path.as_posix()}. Override it?",
            default=False,
        )
        .skip_if(not cfg_exists, default=True)
        .unsafe_ask()
    )

    if not override_config:
        print("Got it, exiting...")
        raise SystemExit(0)

    answers = {}
    answers["container"] = _container_questionnaire(
        prev_cfg.container if cfg_exists else None
    )
    answers["projects"] = _projects_questionnaire(
        prev_cfg.projects if cfg_exists else None
    )

    return Config.model_validate(answers)


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
    ).unsafe_ask()

    if not chosen:
        no_projects = questionary.confirm(
            "No projects selected. Continue?", default=False
        ).unsafe_ask()
        if no_projects:
            return ProjectsConfig()

        print("Got it, exiting...")
        raise SystemExit(0)

    projects_cfg = {}
    for p in chosen:
        print(f"[bold blue]{p}[/bold blue] settings:")
        projects_cfg[p] = questionary.unsafe_prompt(
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


def _default_project_config(name: str) -> Dict[str, Any]:
    return {
        "path": Path(name),
        "origin_url": Url(f"https://gitcode.com/Cangjie/{name}.git"),
        "upstream_url": Url(f"https://gitcode.com/Cangjie/{name}.git"),
        "default_branch": "dev",
    }


def _container_questionnaire(
    prev_cfg: Optional[ContainerConfig] = None,
) -> ContainerConfig:
    placeholders = {
        "use_container": False,
        "container_name": "cjdev",
        "container_workdir": Path.cwd(),
    }
    if prev_cfg:
        placeholders.update(prev_cfg.model_dump(exclude_none=True))

    questions = [
        {
            "type": "confirm",
            "name": "use_container",
            "message": "Do you want to use a docker container for building?",
            "default": placeholders["use_container"],
        },
        {
            "type": "text",
            "name": "container_name",
            "message": "Container name:",
            "default": placeholders["container_name"],
            "when": lambda answers: answers["use_container"],
        },
        {
            "type": "text",
            "name": "container_workdir",
            "message": "Container working directory:",
            "default": placeholders["container_workdir"].as_posix(),
            "when": lambda answers: answers["use_container"],
        },
    ]

    container_cfg = questionary.unsafe_prompt(questions)

    if not container_cfg["use_container"] and prev_cfg:
        prev_cfg.use_container = False
        return prev_cfg

    return ContainerConfig.model_validate(container_cfg)
