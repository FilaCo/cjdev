"""Running a command on this machine."""

import os
import subprocess
from typing import final

from cjdev.application.ports import Command, Completed
from cjdev.errors import CommandError


@final
class HostExecutor:
    def run(self, command: Command, *, check: bool = True) -> Completed:
        # Captured rather than streamed to the terminal: under a fan-out the
        # output of six projects has to be emitted whole and in manifest
        # order, which is impossible once it has already been printed.
        try:
            finished = subprocess.run(
                list(command.argv),
                cwd=command.cwd,
                env={**os.environ, **command.env} if command.env else None,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as failure:
            # A missing binary or a missing cwd arrives as an errno, and an
            # errno reaching the user is the bare traceback we never print.
            raise CommandError(
                argv=command.argv,
                cwd=str(command.cwd),
                exit_code=127,
                output=str(failure),
            ) from failure
        result = Completed(
            command, finished.returncode, finished.stdout, finished.stderr
        )
        if check and not result.ok:
            raise CommandError(
                argv=command.argv,
                cwd=str(command.cwd),
                exit_code=result.exit_code,
                output=result.stderr or result.stdout,
            )
        return result
