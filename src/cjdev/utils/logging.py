import sys

from loguru import logger


def setup_logger():
    logger.remove()  # remove the default handler
    # TODO: logger setup


def record_patcher(record):
    record["level"].name = record["level"].name.lower()
