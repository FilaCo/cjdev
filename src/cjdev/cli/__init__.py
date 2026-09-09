from typer import Typer

from cjdev.bootstrap import Container

from ._context import CjdevContext, CjdevGroup
from .init import cli as init_cli
from .status import cli as status_cli

cli = Typer(
    cls=CjdevGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)

cli.add_typer(init_cli, cls=CjdevGroup)
cli.add_typer(status_cli, cls=CjdevGroup)


@cli.callback(invoke_without_command=True)
def cli_cb(ctx: CjdevContext) -> None:
    """Cangjie SDK developer utilities."""
    ctx.obj = Container()
