"""The error hierarchy, and the exit codes it maps to.

This module sits *below* `domain/`: it imports nothing of ours, so every layer
may raise from it. Nothing else in `cjdev` is allowed that position.
"""

from typing import final


class CjdevError(Exception):
    """Base class for every error `cjdev` reports rather than crashes on.

    `main()` catches this, prints `str(exc)` and exits with `exit_code`. A
    traceback reaching the user is a defect.
    """

    exit_code = 1


@final
class UsageError(CjdevError):
    """The invocation itself is wrong - bad flag, bad name, bad path."""

    exit_code = 2


class PreconditionError(CjdevError):
    """The command is well-formed but the world is not ready for it."""

    exit_code = 3


@final
class ManifestError(PreconditionError):
    """The manifest is unreadable, unsupported or internally inconsistent.

    Includes the refusal of a schema version this cjdev does not understand.
    """


@final
class NotImplementedYetError(CjdevError):
    """A command that is wired up but has no implementation behind it yet.

    Temporary by construction: every instance is removed by the milestone that
    implements the command.
    """

    def __init__(self, what: str, milestone: str) -> None:
        super().__init__(f"{what} is not implemented yet - it lands in {milestone}.")


@final
class CommandError(CjdevError):
    """An external command exited non-zero.

    Carries the argv, the working directory and the tail of the output so the
    CLI can report all three; a bare traceback is a defect.
    """

    TAIL_LINES = 20

    def __init__(
        self, argv: tuple[str, ...], cwd: str, exit_code: int, output: str
    ) -> None:
        self.argv = argv
        self.cwd = cwd
        self.command_exit_code = exit_code
        self.output = output
        tail = "\n".join(output.strip().splitlines()[-self.TAIL_LINES :])
        super().__init__(
            f"{' '.join(argv)}\n  in {cwd}\n  exited {exit_code}"
            + (f"\n{tail}" if tail else "")
        )


@final
class AbortedError(CjdevError):
    """The user declined a confirmation, or interrupted a prompt.

    Not an error in the usual sense, but it must not be mistaken for success:
    exit code 1 says the operation did not happen.
    """

    def __init__(self, what: str) -> None:
        super().__init__(f"{what}: aborted, nothing was changed.")
