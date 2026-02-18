import warnings
import subprocess
from subprocess import Popen

from typer import Context, Typer

from cjdev.commands.build.context import BuildContext

cli = Typer()


@cli.command()
@cli.command("compiler", hidden=True)
def cjc(ctx: Context):
    """Build compiler."""
    build_ctx = ctx.ensure_object(BuildContext)
