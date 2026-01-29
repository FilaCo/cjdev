from logging import error, info
from pathlib import Path
from typing import Any, Dict, Optional

import questionary
from pydantic import ValidationError
from pydantic_core import Url
from questionary import Choice
from rich import print
from typer import Context, Typer

from cjdev.commands.context import (
    CjDevContext,
    Config,
    ProjectsConfig,
)
from cjdev.utils.version import VERSION_TYPE_DEF

cli = Typer()


@cli.command()
def init(ctx: Context, version: VERSION_TYPE_DEF = False):
    """Init cjdev environment."""
    cjdev_ctx = ctx.ensure_object(CjDevContext)
    _init(cjdev_ctx)


def _init(cjdev_ctx: CjDevContext):
    cfg_path = cjdev_ctx.config_path
    config = _init_config(cfg_path, cjdev_ctx.config)
    # TODO: init container
    # TODO: init git
    cjdev_ctx.config = config


def _init_config(cfg_path: Path, prev_cfg: Config) -> Config:
    try:
        answers = questionary.unsafe_prompt(
            _questions(cfg_path, prev_cfg if cfg_path.exists() else None),
            true_color=True,
        )

        if not _override_config(answers):
            info("Cancelled by user")
            return prev_cfg

        raw_cfg = {"container": {}, "projects": {}}
        # collect container configuration
        use_container = answers["use_container"]
        raw_cfg["container"]["use_container"] = use_container
        if use_container:
            raw_cfg["container"]["container_name"] = answers["container_name"]
            raw_cfg["container"]["container_workdir"] = answers["container_workdir"]
        elif cfg_path.exists() and prev_cfg.container:
            raw_cfg["container"]["container_name"] = prev_cfg.container.container_name
            raw_cfg["container"]["container_workdir"] = (
                prev_cfg.container.container_workdir
            )

        # collect project configuration
        chosen_projects = (
            answers["chosen_projects"] if answers["chosen_projects"] else []
        )
        gc_user = answers["gitcode_user"]
        default_branch = answers["default_branch"]
        for project_name in chosen_projects:
            raw_cfg["projects"][project_name] = {
                "path": project_name,
                "origin_url": Url(f"https://gitcode.com/{gc_user}/{project_name}.git"),
                "upstream_url": Url(f"https://gitcode.com/Cangjie/{project_name}.git"),
                "default_branch": default_branch,
            }

        # validate and save
        cfg = Config.model_validate(raw_cfg)
        cfg.save(cfg_path)
        info(f"Config saved successfully at {cfg_path.as_posix()}!")
        return cfg
    except KeyboardInterrupt:
        info("Cancelled by user")
        return prev_cfg
    except ValidationError as e:
        error(f"Incorrect project configuration:\n{e}")
        exit(1)


def _override_config(answers: Dict[str, Any]):
    return "override_config" not in answers or answers["override_config"]


def _questions(cfg_path: Path, prev_cfg: Optional[Config]):
    prechecked_projects = ["cangjie_compiler", "cangjie_runtime"]
    container_cfg_defaults = {
        "use_container": False,
        "container_name": "cjdev",
        "container_workdir": Path.cwd(),
    }
    if prev_cfg:
        if prev_cfg.projects:
            projects_dump = prev_cfg.projects.model_dump(exclude_none=True)
            prechecked_projects = (
                projects_dump.keys()
                if len(projects_dump.keys()) > 0
                else prechecked_projects
            )
        if prev_cfg.container:
            container_cfg_defaults.update(
                prev_cfg.container.model_dump(exclude_none=True)
            )

    return [
        {
            "type": "confirm",
            "name": "override_config",
            "message": f"Override an existing configuration at {cfg_path.as_posix()}?",
            "default": False,
            "when": lambda _: cfg_path.exists(),
        },
        {
            "type": "confirm",
            "name": "use_container",
            "message": "Do you want to use a docker container for building?",
            "default": container_cfg_defaults["use_container"],
            "when": _override_config,
        },
        {
            "type": "text",
            "name": "container_name",
            "message": "Container name:",
            "default": container_cfg_defaults["container_name"],
            "when": lambda answers: _override_config(answers)
            and answers["use_container"],
        },
        {
            "type": "text",
            "name": "container_workdir",
            "message": "Container working directory:",
            "default": container_cfg_defaults["container_workdir"].as_posix(),
            "when": lambda answers: _override_config(answers)
            and answers["use_container"],
        },
        {
            "type": "checkbox",
            "name": "chosen_projects",
            "message": "Select projects to setup:",
            "choices": list(
                map(
                    lambda p: Choice(p, checked=p in prechecked_projects),
                    ProjectsConfig.model_fields,
                )
            ),
            "when": _override_config,
            "validate": lambda chosen_projects: len(chosen_projects) > 0,
        },
        {
            "type": "text",
            "name": "default_branch",
            "message": "Default branch:",
            "default": "dev",
            "when": lambda answers: _override_config(answers)
            and answers["chosen_projects"],
        },
        {
            "type": "text",
            "name": "gitcode_user",
            "message": "Your gitcode username:",
            "when": lambda answers: _override_config(answers)
            and answers["chosen_projects"],
            "validate": lambda username: len(username) > 0,
        },
    ]
