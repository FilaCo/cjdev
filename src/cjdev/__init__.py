from cjdev.commands import cli
from cjdev.utils.logging import setup_logger


def main() -> None:
    setup_logger()
    cli()
