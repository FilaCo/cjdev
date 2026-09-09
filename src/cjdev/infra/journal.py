"""The workspace's own record of what the mutating commands did.

`-v` answers "what is it running?" while you watch. This answers the question
that only gets asked afterwards - "what did `cjdev init` actually do to my
repositories, an hour ago, before it failed?" - which is why it is always on
rather than behind a flag: nobody enables a log for the run they did not yet
know would go wrong.

One appended file, `.cjdev/log/cjdev.log`, so that following it is a single
`tail -f` and the history of a workspace is one place. It lives inside the
workspace, so whatever removes the workspace takes the log with it: the record
of a workspace goes when the workspace does.

Best-effort by construction: a failure to write a log line must never be the
reason a command fails, so every write swallows its own errors.
"""

import contextlib
import os
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import IO, final

from cjdev.domain.layout import WorkspaceLayout

MAX_BYTES = 2 * 1024 * 1024
"""Rotated at, not truncated to. One backup is kept, which is enough to cover
"the run before the one that broke it" without turning into an archive nobody
prunes."""


@final
class CommandJournal:
    """An open append handle on one workspace's log.

    Opened once per command and closed at the end, so that a fan-out's worker
    threads share a handle rather than racing to open the same file. Writes
    are serialised by holding the whole line back until it is complete, which
    a line-buffered text handle does for us at these sizes.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._file: IO[str] | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_large()
            self._file = path.open("a", encoding="utf-8", buffering=1)
        except OSError:
            # A read-only or full disk is not a reason to refuse to work.
            self._file = None

    def write(self, line: str) -> None:
        if self._file is None:
            return
        try:
            self._file.write(f"{_now()} {line}\n")
        except OSError:
            self._file = None

    def close(self) -> None:
        if self._file is not None:
            with contextlib.suppress(OSError):
                self._file.close()
            self._file = None

    def __enter__(self) -> "CommandJournal":
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()

    def _rotate_if_large(self) -> None:
        if self._path.is_file() and self._path.stat().st_size >= MAX_BYTES:
            self._path.replace(self._path.with_suffix(f"{self._path.suffix}.1"))


def open_journal(root: Path, argv: Sequence[str]) -> CommandJournal:
    """Start a log entry for one invocation, headed by the invocation itself.

    The header is what makes an appended file readable: without it, a run that
    fetched six projects is forty lines with no boundary against the run
    before it.
    """
    journal = CommandJournal(Path(WorkspaceLayout(root).command_log))
    journal.write(f"--- cjdev {' '.join(argv)}  # cwd={Path.cwd()} pid={os.getpid()}")
    return journal


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
