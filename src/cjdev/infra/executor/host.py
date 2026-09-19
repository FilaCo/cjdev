"""Running a command on this machine."""

import os
import subprocess
from collections import deque
from contextlib import ExitStack
from pathlib import Path, PurePath
from typing import final

from cjdev.application.ports import Command, Completed
from cjdev.errors import CommandError, PreconditionError

TAIL_LINES = 100
"""How much of a logged command's output is kept in memory.

Above what any rendering shows (`CommandError` prints twenty) and far below a
build's real output, which is what the log file is for. A bound rather than the
whole thing, because a forty-minute compile is measured in hundreds of
megabytes.
"""


@final
class HostExecutor:
    def run(self, command: Command, *, check: bool = True) -> Completed:
        log = command.log
        if command.interactive:
            result = self._attached(command)
        elif log is not None:
            result = self._teed(command, log)
        else:
            result = self._captured(command)
        if check and not result.ok:
            raise CommandError(
                argv=command.argv,
                cwd=str(command.cwd),
                exit_code=result.exit_code,
                output=result.stderr or result.stdout,
            )
        return result

    def _captured(self, command: Command) -> Completed:
        # Captured rather than streamed to the terminal: under a fan-out the
        # output of six projects has to be emitted whole and in manifest
        # order, which is impossible once it has already been printed.
        try:
            finished = subprocess.run(
                list(command.argv),
                cwd=command.cwd,
                env=self._env(command),
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as failure:
            raise self._unstartable(command, failure) from failure
        return Completed(command, finished.returncode, finished.stdout, finished.stderr)

    def _attached(self, command: Command) -> Completed:
        """The terminal, as it is: no pipes, so a shell has a tty, a build run
        by hand paints its own progress, and Ctrl-C reaches the child because
        it is in this process group.

        Nothing is captured, so nothing comes back. A `Completed` with empty
        output is the honest shape here, and the caller that wanted a
        transcript should not have asked for the terminal.
        """
        try:
            finished = subprocess.run(
                list(command.argv),
                cwd=command.cwd,
                env=self._env(command),
                check=False,
            )
        except OSError as failure:
            raise self._unstartable(command, failure) from failure
        return Completed(command, finished.returncode, "", "")

    def _teed(self, command: Command, log_file: PurePath) -> Completed:
        """Into the unit's log while it runs, with only the tail coming back.

        Streamed rather than captured and written afterwards, because the log
        exists to be tailed during the build - a file that appears once the
        build has already died is the failure mode it is meant to fix. stderr
        is folded into stdout so the log reads in the order things happened.
        """
        tail: deque[str] = deque(maxlen=TAIL_LINES)
        with ExitStack() as closing:
            try:
                # Line-buffered: anything larger and `tail -f` shows nothing
                # for minutes at a time. Opened in its own `try` so that a log
                # this process cannot write is not reported as a command that
                # would not start - the second sends the reader looking at
                # their build script for what is a full disk.
                log = closing.enter_context(
                    Path(log_file).open("a", encoding="utf-8", buffering=1)
                )
            except OSError as failure:
                raise self._unwritable(log_file, failure) from failure
            try:
                process = closing.enter_context(
                    subprocess.Popen(
                        list(command.argv),
                        cwd=command.cwd,
                        env=self._env(command),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                    )
                )
            except OSError as failure:
                raise self._unstartable(command, failure) from failure
            for line in process.stdout or ():
                try:
                    log.write(line)
                except OSError as failure:
                    # A disk that fills mid-build is the same failure as a log
                    # that would not open, and neither is the build failing.
                    raise self._unwritable(log_file, failure) from failure
                tail.append(line.rstrip("\n"))
        return Completed(command, process.returncode, "\n".join(tail), "")

    @staticmethod
    def _env(command: Command) -> dict[str, str] | None:
        return {**os.environ, **command.env} if command.env else None

    @staticmethod
    def _unwritable(log_file: PurePath, failure: OSError) -> PreconditionError:
        """The build log is not the build: an unwritable one has to say so, or
        the reader goes looking at their build script for a full disk."""
        return PreconditionError(f"cannot write the build log {log_file}: {failure}")

    @staticmethod
    def _unstartable(command: Command, failure: OSError) -> CommandError:
        """A missing binary or a missing cwd arrives as an errno, and an errno
        reaching the user is the bare traceback we never print."""
        return CommandError(
            argv=command.argv,
            cwd=str(command.cwd),
            exit_code=127,
            output=str(failure),
        )
