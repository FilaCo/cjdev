"""What the application layer requires of the outside world.

`Executor`, `FileSystem` and `Prompt` live here. `Forge` joins them in M5; it is absent
rather than stubbed, because an empty protocol tells a reader nothing and
invites guessing at a shape the gitcode spike has not settled yet (R6).

Git is deliberately not a port: NFR-3 already commits to driving the `git`
CLI, and the CLI runs through `Executor`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Protocol, final


@final
@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str] = field(default_factory=dict)
    mutates: bool = True
    """Read-only commands survive `--dry-run`; mutating ones are printed
    instead of run. A dry run that could not inspect the world would have
    nothing to decide from, and would print a plan built on guesses (UX-1).

    It defaults to `True` so that forgetting to classify a command makes the
    dry run too cautious rather than destructive.
    """


@final
@dataclass(frozen=True)
class Completed:
    command: Command
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class Executor(Protocol):
    def run(self, command: Command, *, check: bool = True) -> Completed: ...


class Prompt(Protocol):
    """Asking the person running the command.

    A port because it has two real implementations, not because tests need a
    seam: `--yes`, a pipe and `--dry-run` all have to answer without a
    terminal, and that is a different behaviour rather than a stub.

    Use cases call this between deciding and applying, so no worker ever
    prompts from inside a fan-out (PAR-6).
    """

    def confirm(self, question: str, *, destructive: bool = True) -> bool:
        """`destructive` defaults to True so that a forgotten classification
        makes a command ask too often rather than act unasked (UX-2)."""
        ...

    def choose(
        self, question: str, options: Sequence[str], *, preselected: Sequence[str]
    ) -> tuple[str, ...]: ...


class FileSystem(Protocol):
    """Changing the workspace tree itself.

    A port for the same reason `Executor` is one: `--dry-run` is a MUST on
    every mutating command (UX-1), and a use case that calls `Path.mkdir`
    directly escapes it. Reads are not here - a probe is always real, exactly
    as read-only commands are (see `Command.mutates`).
    """

    def mkdir(self, path: PurePath) -> None: ...

    def write_text(self, path: PurePath, text: str) -> None: ...

    def remove(self, path: PurePath) -> None:
        """A file or a whole directory: callers delete what is there, and the
        distinction is the filesystem's business rather than theirs."""
        ...
