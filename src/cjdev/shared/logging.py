from rich.logging import RichHandler
import logging
import logging.config
from pathlib import Path
from typing import Dict

from rich.console import Console

_LOG_DIR = "logs"
_LOG_FILE_NAME = "cjdev.log"


def init_logging(home_path: Path, level: int):
    log_dir = home_path / _LOG_DIR
    log_dir.mkdir(exist_ok=True, parents=True)
    log_file = log_dir / _LOG_FILE_NAME

    console_handler = RichHandler(markup=True, show_time=False, rich_tracebacks=True)
    console_handler.setLevel(max(logging.WARNING, level))

    file_handler = RichHandler(console=Console(file=open(log_file, "a")))
    file_handler.setLevel(level)

    logging.basicConfig(format="%(message)s", handlers=[console_handler, file_handler])
