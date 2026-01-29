import sys

from loguru import logger


def setup_logger():
    logger.remove()  # remove the default handler
    logger.configure(patcher=record_patcher)
    logger.add(
        sys.stderr,
        format="<lvl>{level}</lvl>: {message}\n",
        level="ERROR",
    )


def record_patcher(record):
    record["level"].name = record["level"].name.lower()
