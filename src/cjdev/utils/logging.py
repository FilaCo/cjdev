import logging
from pathlib import Path
from typing import Optional, Union

from rich.console import Console
from rich.logging import RichHandler

_LOG_DIR = "logs"
_LOG_FILE_NAME = "cjdev.log"


def init_logging(
    pwd: Optional[Path] = None, level: Union[int, str] = logging.INFO
) -> logging.Logger:
    logger = logging.getLogger()
    logger.setLevel(level)

    warning_handler = RichHandler(markup=True, show_time=False)
    warning_handler.setLevel(max(logging.WARNING, logger.level))
    logger.addHandler(warning_handler)

    if pwd:
        file_handler = _init_file_handler(pwd, level)
        logger.addHandler(file_handler)
    return logger


def _init_file_handler(pwd: Path, level: Union[int, str]) -> logging.Handler:
    """
    Init file handler with given path.
    Args:
        pwd (Path): Path to the working directory.
    """
    log_dir = pwd / _LOG_DIR
    log_dir.mkdir(exist_ok=True, parents=True)
    log_file = log_dir / _LOG_FILE_NAME
    file_handler = RichHandler(console=Console(file=open(log_file, "a")))
    file_handler.setLevel(level)
    return file_handler
