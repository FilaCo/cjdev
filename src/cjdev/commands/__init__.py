from typer import Typer

from .status import cli as status_cli

cli = Typer(
    context_settings={"help_option_names": ["-h", "--help"]}, no_args_is_help=True
)

cli.add_typer(status_cli)


@cli.callback()
def cli_cb() -> None:
    """Cangjie's developer utilities."""
