"""The error hierarchy, the exit codes it maps to, and the codes a caller reads.

This module sits *below* `domain/`: it imports nothing of ours, so every layer
may raise from it. Nothing else in `cjdev` is allowed that position.

Two identifiers travel with a failure, and they answer different questions.
The **exit code** says which *kind* of failure it was; there are four, and a
shell script branches on them. The **code** says which failure it was, survives
a reworded message, and is what something parsing `--json` matches on. Both are
listed here because a caller has to look them up in one place:

| code | exit | raised when |
| --- | --- | --- |
| `failed` | 1 | the operation did not complete |
| `usage` | 2 | the invocation itself is wrong |
| `precondition` | 3 | the command is well-formed, the world is not ready |
| `manifest` | 3 | the manifest is unreadable, unsupported or inconsistent |
| `input_required` | 3 | an answer is needed and there is no terminal to ask at |
| `aborted` | 1 | the user declined, or interrupted a prompt |
| `command_failed` | 1 | an external command exited non-zero |
| `not_implemented` | 1 | the command is wired up but lands in a later milestone |
"""

from typing import final


class CjdevError(Exception):
    """Base class for every error `cjdev` reports rather than crashes on.

    `main()` catches this, renders it and exits with `exit_code`. A traceback
    reaching the user is a defect.
    """

    exit_code = 1
    code = "failed"

    def __init__(
        self, message: str, *, subject: str | None = None, remedy: str | None = None
    ) -> None:
        super().__init__(message)
        self.subject = subject
        """The project or build unit this belongs to, when it belongs to one.
        A fan-out over six projects reports six failures, and "which one" is
        not something a caller should have to find by reading the message."""
        self.remedy = remedy
        """The command that resolves or resumes this, when one exists. A caller
        with no terminal recovers from what the output states and from nothing
        else - which also means an invented remedy is worse than no remedy, so
        this stays None unless there is a real one to name."""

    def details(self) -> dict[str, object]:
        """Whatever else this kind of failure can say in machine-readable form.

        Empty by default: the fields below are a contract, and a subclass that
        has nothing structured to add must not invent something to fill it.
        """
        return {}


@final
class UsageError(CjdevError):
    """The invocation itself is wrong - bad flag, bad name, bad path."""

    exit_code = 2
    code = "usage"


class PreconditionError(CjdevError):
    """The command is well-formed but the world is not ready for it."""

    exit_code = 3
    code = "precondition"


@final
class ManifestError(PreconditionError):
    """The manifest is unreadable, unsupported or internally inconsistent.

    Includes the refusal of a schema version this cjdev does not understand.
    """

    code = "manifest"


@final
class InputRequiredError(PreconditionError):
    """An answer is needed, and there is nothing to ask.

    Its own class because it is the one failure an unattended caller can always
    fix from the output alone, and the fix is a flag: `remedy` is required
    rather than optional here.
    """

    code = "input_required"

    def __init__(self, question: str, *, remedy: str) -> None:
        super().__init__(question, remedy=remedy)


@final
class NotImplementedYetError(CjdevError):
    """A command that is wired up but has no implementation behind it yet.

    Temporary by construction: every instance is removed by the milestone that
    implements the command.
    """

    code = "not_implemented"

    def __init__(self, what: str, milestone: str) -> None:
        super().__init__(f"{what} is not implemented yet - it lands in {milestone}.")
        self.milestone = milestone

    def details(self) -> dict[str, object]:
        return {"milestone": self.milestone}


@final
class CommandError(CjdevError):
    """An external command exited non-zero.

    Carries the argv, the working directory and the tail of the output so the
    CLI can report all three; a bare traceback is a defect.
    """

    code = "command_failed"

    TAIL_LINES = 20

    def __init__(
        self, argv: tuple[str, ...], cwd: str, exit_code: int, output: str
    ) -> None:
        self.argv = argv
        self.cwd = cwd
        self.command_exit_code = exit_code
        self.output = output
        self.tail = "\n".join(output.strip().splitlines()[-self.TAIL_LINES :])
        super().__init__(
            f"{' '.join(argv)}\n  in {cwd}\n  exited {exit_code}"
            + (f"\n{self.tail}" if self.tail else "")
        )

    def details(self) -> dict[str, object]:
        """The tail rather than the whole output, in both renderings.

        A failing build prints thousands of lines, and a caller that has to
        hold all of them to find the last twenty is being charged for the
        transcript twice.
        """
        return {
            "argv": list(self.argv),
            "cwd": self.cwd,
            "command_exit_code": self.command_exit_code,
            "output_tail": self.tail,
        }


@final
class AbortedError(CjdevError):
    """The user declined a confirmation, or interrupted a prompt.

    Not an error in the usual sense, but it must not be mistaken for success:
    exit code 1 says the operation did not happen.
    """

    code = "aborted"

    def __init__(self, what: str) -> None:
        super().__init__(f"{what}: aborted, nothing was changed.")
