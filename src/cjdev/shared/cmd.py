from subprocess import Popen, CompletedProcess
from typing import final, List, Dict
from pydantic import BaseModel
from logging import getLogger

logger = getLogger(__name__)

# def execute_with_log(args: List[str], logger: logging.Logger):
#     with Progress(
#         SpinnerColumn(), TextColumn("{task.description}"), TimeElapsedColumn()
#     ) as overall_progress:
#         overall_progress.add_task(description=f"Executing command: `{args}`")
#         process = subprocess.Popen(
#             args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
#         )

#         if not process.stdout:
#             logger.error(f"Failed to execute command: `{args}`")
#             raise typer.Exit(1)

#         _log_process_output(process.stdout, logger)

#         exitcode = process.wait()
#         if exitcode:
#             logger.error(f"Command failed with exit code {exitcode}: `{args}`")
#             raise typer.Exit(exitcode)


# def _log_process_output(output: IO[str], logger: logging.Logger):
#     render = get_render_func()
#     with Live() as live:
#         for line in map(lambda x: x.rstrip(), output):
#             logger.debug(line)
#             live.update(render(line))


# def get_render_func(rows: int = 5):
#     lines = []

#     def render_lines(line: str) -> RenderableType:
#         lines.append(line)

#         if len(lines) > rows:
#             lines.pop(0)

#         output = Padding("\n".join(lines), (0, 4))
#         return output

#     return render_lines
