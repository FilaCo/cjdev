import logging
import shlex
import subprocess
from typing import IO


def execute(cmd: str, logger: logging.Logger):
    args = shlex.split(cmd)

    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if not p.stdout:
        logger.error(f"Failed to execute command: {cmd}")
        return

    with p.stdout:
        _log_process_output(p.stdout, logger)

    exitcode = p.wait()
    if exitcode != 0:
        logger.error(f"Command failed with exit code {exitcode}: {cmd}")


def _log_process_output(output: IO[bytes], logger: logging.Logger):
    for line in iter(output.readline, b"\n"):
        logging.info(line)
