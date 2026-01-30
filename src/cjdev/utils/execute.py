import logging
import shlex
import subprocess
import sys
import time
from typing import IO

import typer
from rich.console import RenderableType
from rich.live import Live
from rich.padding import Padding
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, track
from rich.table import Table


def execute(cmd: str, logger: logging.Logger):
    args = shlex.split(cmd)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), TimeElapsedColumn()
    ) as overall_progress:
        overall_progress.add_task(description=f"Executing command: `{cmd}`")
        process = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        if not process.stdout:
            logger.error(f"Failed to execute command: `{cmd}`")
            raise typer.Exit(1)

        _log_process_output(process.stdout, logger)

        exitcode = process.wait()
        if exitcode:
            logger.error(f"Command failed with exit code {exitcode}: `{cmd}`")
            raise typer.Exit(exitcode)


def _log_process_output(output: IO[bytes], logger: logging.Logger):
    render = get_render_func()
    with Live() as live:
        for line in iter(output.readline, b""):
            live.update(render(line))


def get_render_func(rows: int = 5):
    lines = []

    def render_lines(byte_str: bytes) -> RenderableType:
        try:
            line = byte_str.decode("ascii", "ignore").rstrip()
        except UnicodeDecodeError:
            line = byte_str.decode("utf-8", "ignore").rstrip()

        line = f"[bright_black]{line}[/]"
        lines.append(line)

        if len(lines) > rows:
            lines.pop(0)

        output = Padding("\n".join(lines), (0, 4))
        return output

    return render_lines
