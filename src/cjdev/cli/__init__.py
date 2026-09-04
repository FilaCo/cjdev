from typer import Typer

from ._container import Container
from ._context import CjdevContext, CjdevGroup
from .build import cli as build_cli
from .init import cli as init_cli
from .status import cli as status_cli

cli = Typer(
    cls=CjdevGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)

cli.add_typer(init_cli, cls=CjdevGroup)
cli.add_typer(status_cli, cls=CjdevGroup)
cli.add_typer(
    build_cli, cls=CjdevGroup, name="build", help="Build Cangjie SDK projects."
)


@cli.callback(invoke_without_command=True)
def cli_cb(ctx: CjdevContext) -> None:
    """Cangjie's developer utilities."""
    ctx.obj = Container()
