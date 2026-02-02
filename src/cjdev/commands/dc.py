import logging
import shutil
import subprocess
from pathlib import Path
from typing import Annotated, List, Optional

import questionary
from typer import Argument, Context, Typer

from cjdev.assets import DOCKERFILE
from cjdev.commands.context import CjDevContext, ContainerConfig
from cjdev.utils.execute import execute_with_log
from cjdev.utils.logging import MESSAGE

cli = Typer()


@cli.command(context_settings={"ignore_unknown_options": True})
def dc(
    ctx: Context,
    args: Annotated[Optional[List[str]], Argument()] = None,
):
    """Execute a command in the container."""
    cjdev_ctx = ctx.ensure_object(CjDevContext)
    _dc(cjdev_ctx, args)


_CONTAINER_WORKDIR = "/home/cjdev"


def _dc(cjdev_ctx: CjDevContext, args: Annotated[Optional[List[str]], Argument()]):
    config = cjdev_ctx.config
    container_cfg = config.container
    logger = cjdev_ctx.logger
    if not container_cfg.use_container:
        logger.log(
            MESSAGE,
            "Seems like you're [bold red]not[/] using a container. Set 'use_container' to true in your config file and repeat the command.",
        )

        return

    try:
        _check_prerequisites()
    except Exception as e:
        logger.error(f"Unable to run command in the container.\n{e}")
        return

    host_workdir = cjdev_ctx.config_path.parent
    container_pwd = _container_pwd(host_workdir, Path.cwd())
    container_name = container_cfg.container_name
    _exec_cmd_in_container(
        args or ["zsh"], host_workdir, container_pwd, container_name or "cjdev"
    )


def _exec_cmd_in_container(
    cmd: List[str], host_workdir: Path, container_pwd: Path, container_name: str
):
    cmd = [
        "container",
        "run",
        "-it",
        "--rm",
        "-v",
        f"{host_workdir.as_posix()}:{_CONTAINER_WORKDIR}:rw",
        "-w",
        container_pwd.as_posix(),
        container_name or "cjdev",
        "bash",
        "-lc",
        " ".join(cmd),
    ]
    subprocess.run(args=cmd, executable="docker")


def _container_pwd(host_workdir: Path, host_pwd: Path) -> Path:
    # Cut the prefix
    # /home/filaco/Projects/cjdev/a/b/c -> /a/b/c
    relpath = host_pwd.as_posix().removeprefix(host_workdir.as_posix())
    return Path(_CONTAINER_WORKDIR) / relpath


def init_container(cfg_path: Path, cfg: ContainerConfig, logger: logging.Logger):
    if not cfg.use_container:
        return

    try:
        _check_prerequisites()
    except Exception as e:
        logger.error(f"Unable to initialize container.\n{e}")
        return

    dockerfile = cfg_path.parent / "Dockerfile"
    override_dockerfile = questionary.confirm(
        f"Override an existing Dockerfile at {dockerfile.as_posix()}?",
        default=False,
    ).unsafe_ask()
    if override_dockerfile:
        dockerfile.write_text(DOCKERFILE)
    _build_container(cfg, dockerfile, logger)


def build_container(cfg: ContainerConfig, dockerfile: Path, logger: logging.Logger):
    try:
        _check_prerequisites()
    except Exception as e:
        logger.error(f"Unable to build container.\n{e}")
        return

    _build_container(cfg, dockerfile, logger)


def _build_container(cfg: ContainerConfig, dockerfile: Path, logger: logging.Logger):
    container_name = cfg.container_name if cfg.container_name else "cjdev"
    execute_with_log(
        ["docker", "build", "-t", container_name, dockerfile.parent.as_posix()],
        logger,
    )


def _check_prerequisites():
    if not shutil.which("docker"):
        raise Exception("`docker` is not installed")
