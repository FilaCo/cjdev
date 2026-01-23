import importlib.metadata
from typing import Annotated

from rich import print
from typer import Context, Exit, Option, Typer

from cjdev.commands.build import cli as build_cli
from cjdev.commands.context import CjDevContext, Config
from cjdev.commands.dc import cli as dc_cli
from cjdev.commands.git import cli as git_cli
from cjdev.commands.init import cli as init_cli
from cjdev.commands.status import cli as status_cli
from cjdev.commands.test import cli as test_cli

cli = Typer(
    context_settings={"help_option_names": ["-h", "--help"]}, no_args_is_help=True
)

cli.add_typer(status_cli)
cli.add_typer(init_cli)
cli.add_typer(build_cli, name="build")
cli.add_typer(test_cli, name="test")
cli.add_typer(git_cli, name="git")
cli.add_typer(dc_cli)


@cli.callback(invoke_without_command=True)
def cli_cb(
    ctx: Context,
    version: Annotated[
        bool | None, Option("--version", "-V", help="Print version info and exit.")
    ] = None,
):
    """Cangjie's developer utilities."""
    if version:
        print(f"cjdev {importlib.metadata.version('cjdev')}")
        raise Exit()

    if ctx.invoked_subcommand:
        (config_path, config) = Config.load_or_default()
        ctx.obj = CjDevContext(config_path=config_path, config=config)
