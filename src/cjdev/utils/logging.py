import sys

from loguru import logger


def setup_logger():
    logger.remove()  # remove the default handler
    logger.configure(extra={"command": "cjdev"})
    logger.add(
        sys.stderr,
        format="{extra[command]}:<lvl>{level}</lvl>:{message}\n{exception}",
        level="WARNING",
    )
