import shutil
import subprocess
from typing import Annotated, List, Optional

from rich import print
from typer import Argument, Context, Typer

from cjdev.commands.context import CjDevContext
from cjdev.utils.version import VERSION_TYPE_DEF

cli = Typer()


@cli.command(context_settings={"ignore_unknown_options": True})
def dc(
    ctx: Context,
    version: VERSION_TYPE_DEF = False,
    args: Annotated[Optional[List[str]], Argument()] = None,
):
    """Execute a command in the container."""
    cjdev_ctx = ctx.ensure_object(CjDevContext)
    _dc(cjdev_ctx)


def _dc(cjdev_ctx: CjDevContext):
    pass


def build_container():
    pass


def _check_prerequisites():
    if not shutil.which("docker"):
        raise Exception("Docker is not installed")
