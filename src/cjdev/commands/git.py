from typing import Annotated

from typer import Context, Option, Typer

from cjdev.commands.context import CjDevContext

cli = Typer()


@cli.command()
def init(
    ctx: Context,
    branch: Annotated[
        str,
        Option(
            "--branch",
            "-b",
            help="A remote branch for tracking updates",
        ),
    ] = "dev",
):
    """Initialize multi-module git environment"""
    cjdev_ctx = ctx.ensure_object(CjDevContext)
    _init(cjdev_ctx, branch)


def _init(ctx: CjDevContext, branch: str):
    pass


@cli.command()
def status():
    pass


@cli.command()
def switch():
    pass


@cli.command()
def pull():
    pass


@cli.command()
def push():
    pass
