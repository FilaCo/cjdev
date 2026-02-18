import logging
import subprocess
from subprocess import CompletedProcess, Popen
from typing import List, final

from pydantic import BaseModel

logger = logging.getLogger(__name__)


@final
class Process(BaseModel):
    args: List[str]
    cwd: str
    shell: bool = False


def launch(proc: Process) -> Popen[bytes]:
    return Popen(proc.args, cwd=proc.cwd, shell=proc.shell)


def launch_many(procs: List[Process]) -> List[Popen[bytes]]:
    return [launch(proc) for proc in procs]


def run(proc: Process) -> CompletedProcess[bytes]:
    return subprocess.run(proc.args, cwd=proc.cwd, shell=proc.shell)


def run_many(procs: List[Process]) -> List[CompletedProcess[bytes]]:
    """
    Run multiple processes sequentially and return their results.
    """
    return [run(proc) for proc in procs]
