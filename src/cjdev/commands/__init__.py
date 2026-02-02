import logging

from pydantic import ValidationError
from tomlkit.exceptions import ParseError
from typer import Context, Typer

from cjdev.commands.build import cli as build_cli
from cjdev.commands.context import CjDevContext, Config
from cjdev.commands.dc import cli as dc_cli
from cjdev.commands.git import cli as git_cli
from cjdev.commands.init import cli as init_cli
from cjdev.commands.status import cli as status_cli
from cjdev.commands.test import cli as test_cli
from cjdev.utils.logging import init_logging
from cjdev.utils.verbose import VERBOSE_TYPE_DEF
from cjdev.utils.version import VERSION_TYPE_DEF

cli = Typer(
    context_settings={"help_option_names": ["-h", "--help"]}, no_args_is_help=True
)

cli.add_typer(status_cli)
cli.add_typer(init_cli)
cli.add_typer(build_cli, name="build")
cli.add_typer(test_cli, name="test")
cli.add_typer(
    git_cli, name="git", help="Git utils for Cangjie's repositories management."
)
cli.add_typer(dc_cli)


@cli.callback(invoke_without_command=True)
def cli_cb(
    ctx: Context,
    version: VERSION_TYPE_DEF = False,
    verbose: VERBOSE_TYPE_DEF = False,
):
    """Cangjie's developer utilities."""
    config_path = Config.find_config()
    level = logging.DEBUG if verbose else logging.INFO
    logger = init_logging(pwd=config_path.parent, level=level)
    try:
        config = Config.load(config_path)
    except FileNotFoundError as e:
        logger.warning(f"Config file not found.\n{e}")
        config = Config()
    except (ParseError, ValidationError) as e:
        logger.error(f"Config file is invalid.\n{e}")
        config = Config()

    ctx.obj = CjDevContext(
        config_path=config_path, config=config, logger=logger, verbose=verbose
    )
