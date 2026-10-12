from importlib.metadata import version

from typer import Exit, Option, Typer

from cjdev.bootstrap import Container

from ._context import CjdevContext, CjdevGroup
from .branch import cli as branch_cli
from .build import cli as build_cli
from .commit import cli as commit_cli
from .config import cli as config_cli
from .env import cli as env_cli
from .init import cli as init_cli
from .issue import cli as issue_cli
from .push import cli as push_cli
from .status import cli as status_cli
from .test import cli as test_cli

cli = Typer(
    cls=CjdevGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)

cli.add_typer(branch_cli, cls=CjdevGroup)
cli.add_typer(build_cli, cls=CjdevGroup)
cli.add_typer(init_cli, cls=CjdevGroup)
cli.add_typer(status_cli, cls=CjdevGroup)
cli.add_typer(commit_cli, cls=CjdevGroup)
cli.add_typer(push_cli, cls=CjdevGroup)
cli.add_typer(config_cli, cls=CjdevGroup)
cli.add_typer(env_cli, cls=CjdevGroup)
cli.add_typer(test_cli, cls=CjdevGroup)
cli.add_typer(issue_cli, cls=CjdevGroup)


def _print_version(requested: bool) -> None:
    if requested:
        print(f"cjdev {version('cjdev')}")
        raise Exit


@cli.callback(invoke_without_command=True)
def cli_cb(
    ctx: CjdevContext,
    _version: bool = Option(
        False,
        "--version",
        callback=_print_version,
        is_eager=True,
        help="Print the version and exit.",
    ),
) -> None:
    """Cangjie SDK developer utilities."""
    ctx.obj = Container()
