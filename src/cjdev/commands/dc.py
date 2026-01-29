from typer import Context, Typer

from cjdev.commands.context import CjDevContext

cli = Typer()


@cli.command()
def dc(ctx: Context):
    """Execute a command in the container."""
    cjdev_ctx = ctx.ensure_object(CjDevContext)
    _dc(cjdev_ctx)


def _dc(cjdev_ctx: CjDevContext):
    pass


def build_container():
    pass
