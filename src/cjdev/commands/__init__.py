"""Typer wiring. Thin by construction (architecture decision 6).

One module per command, never a subpackage: if a command file grows enough to want a
folder, logic has leaked into it that belongs in `application/`.
"""

from typer import Typer

from .init import cli as init_cli
from .status import cli as status_cli

cli = Typer(
    context_settings={"help_option_names": ["-h", "--help"]}, no_args_is_help=True
)

cli.add_typer(init_cli)
cli.add_typer(status_cli)


@cli.callback()
def cli_cb() -> None:
    """Cangjie's developer utilities."""
