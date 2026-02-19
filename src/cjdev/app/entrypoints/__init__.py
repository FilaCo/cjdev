from typer import Typer

from cjdev.app.options.verbose import VERBOSE_TYPE_DEF
from cjdev.app.options.version import VERSION_TYPE_DEF

from .build import cli as build_cli
from .dc import cli as dc_cli
from .init import cli as init_cli
from .status import cli as status_cli
from .switch import cli as switch_cli
from .sync import cli as sync_cli
from .test import cli as test_cli
from .upload import cli as upload_cli

cli = Typer(
    context_settings={"help_option_names": ["-h", "--help"]}, no_args_is_help=True
)

cli.add_typer(build_cli)
cli.add_typer(dc_cli)
cli.add_typer(init_cli)
cli.add_typer(status_cli)
cli.add_typer(switch_cli)
cli.add_typer(sync_cli)
cli.add_typer(test_cli)
cli.add_typer(upload_cli)


@cli.callback(invoke_without_command=True)
def cli_cb(
    version: VERSION_TYPE_DEF = False,
    verbose: VERBOSE_TYPE_DEF = False,
):
    """Cangjie's developer utilities."""
    pass
