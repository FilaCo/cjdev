from logging import (
    DEBUG,
    INFO,
    WARNING,
    FileHandler,
    Formatter,
    Handler,
    Logger,
    addLevelName,
    getLogger,
)
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

_LOG_DIR = "logs"
_LOG_FILE_NAME = "cjdev.log"


def get_logger(name: Optional[str] = None, pwd: Optional[Path] = None) -> Logger:
    logger = getLogger(name)
    logger.setLevel(INFO)

    warning_handler = RichHandler(markup=True, show_time=False)
    warning_handler.setLevel(WARNING)
    logger.addHandler(warning_handler)

    info_handler = RichHandler(markup=True, show_time=False, show_level=False)
    info_handler.setLevel(INFO)
    info_handler.filters.append(lambda record: record.levelno == INFO)
    logger.addHandler(info_handler)

    if pwd:
        file_handler = _init_file_handler(pwd)
        logger.addHandler(file_handler)
    return logger


def _init_file_handler(pwd: Path) -> Handler:
    """Add file logger to the root logger."""
    log_dir = pwd / _LOG_DIR
    log_dir.mkdir(exist_ok=True, parents=True)
    log_file = log_dir / _LOG_FILE_NAME
    file_handler = RichHandler(console=Console(file=open(log_file, "a")))
    file_handler.setLevel(INFO)  # TODO: env
    return file_handler
