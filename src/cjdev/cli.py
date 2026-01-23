import importlib.metadata
from typing import Annotated

from rich import print
from typer import Exit, Option, Typer

from cjdev.features.build import cli as build_cli
from cjdev.features.dc import cli as dc_cli
from cjdev.features.git import cli as git_cli
from cjdev.features.init import cli as init_cli
from cjdev.features.status import cli as status_cli
from cjdev.features.test import cli as test_cli

cli = Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)

cli.add_typer(status_cli)
cli.add_typer(init_cli)
cli.add_typer(build_cli)
cli.add_typer(test_cli)
cli.add_typer(git_cli)
cli.add_typer(dc_cli)


@cli.callback()
def common_cli(
    version: Annotated[
        bool | None, Option("-V", "--version", help="Print version info and exit.")
    ] = None,
):
    """Cangjie's developer utilities."""
    if version:
        print(f"cjdev {importlib.metadata.version('cjdev')}")
        raise Exit
