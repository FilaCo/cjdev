import logging
import shutil
from pathlib import Path
from typing import Annotated, List, Optional

import questionary
from typer import Argument, Context, Typer

from cjdev.assets import DOCKERFILE
from cjdev.commands.context import CjDevContext, ContainerConfig
from cjdev.utils.execute import execute

cli = Typer()


@cli.command(context_settings={"ignore_unknown_options": True})
def dc(
    ctx: Context,
    args: Annotated[Optional[List[str]], Argument()] = None,
):
    """Execute a command in the container."""
    cjdev_ctx = ctx.ensure_object(CjDevContext)
    _dc(cjdev_ctx)


def _dc(cjdev_ctx: CjDevContext):
    pass


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
    ).ask()
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
    execute(
        f"docker build -t {container_name} {dockerfile.parent.as_posix()}",
        logger,
    )


def _check_prerequisites():
    if not shutil.which("docker"):
        raise Exception("`docker` is not installed")
