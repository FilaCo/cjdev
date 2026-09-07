"""The machine-readable half of a command's output: the `--json` envelope.

`--json` is a contract with something that is not a person, so it is shaped
like one. Every command emits the same envelope - schema version, which command
it was, whether it worked, the payload, the failures - and a caller pins the
version rather than the layout of one command's report (UX-11). Fields are
added and never repurposed; anything else bumps `SCHEMA`.

Written with `print` rather than through `rich`: a renderer that knows about
terminal width, colour and markup has no business anywhere near a document
something else is about to parse, and "remember to pass markup=False" is not a
guarantee. Stdout carries that document and nothing else; the progress display,
the transcript and errors go to stderr (UX-12).

Which mode a run is in is module state, like the consoles in `_console.py` and
for a related reason: the failure path leaves through `main()`, outside Typer's
context, so by the time an error is rendered the only thing left that knows how
the command meant to report is here.
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import final

from rich.console import Console

from cjdev.errors import CjdevError

from ._console import console, diagnostics, print_error

SCHEMA = 1
"""Bumped only by a change that breaks a parser.

A caller that pinned 1 and reads an envelope saying 2 knows to stop rather than
to guess, which is the entire point of the number.
"""


def problem(
    code: str,
    message: str,
    *,
    subject: str | None = None,
    remedy: str | None = None,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """One failure, in the shape UX-13 asks for.

    `subject` and `remedy` are always present, null when there is none: a
    parser that can rely on the key existing is simpler than one that has to
    ask, and a missing key and a null one would otherwise be the same thing.
    """
    return {
        "code": code,
        "message": message,
        "subject": subject,
        "remedy": remedy,
        **dict(details or {}),
    }


def from_error(error: Exception, *, subject: str | None = None) -> dict[str, object]:
    """`subject` is the fallback, not the override.

    The raiser knows more than the caller: a `CommandError` that already named
    a project keeps that name, while one raised deep inside a fan-out gets the
    unit label the runner was tracking it under.
    """
    if isinstance(error, CjdevError):
        return problem(
            error.code,
            str(error),
            subject=error.subject or subject,
            remedy=error.remedy,
            details=error.details(),
        )
    # Nothing below `main()` raises these on purpose, and a caller still has to
    # be able to tell that something went wrong rather than reading an empty
    # errors list next to `ok: false`.
    return problem("failed", str(error) or type(error).__name__, subject=subject)


@final
@dataclass
class Output:
    """How this invocation reports, and the one document it is allowed to
    print if it reports as JSON."""

    command: str = ""
    as_json: bool = False
    _emitted: bool = field(default=False, repr=False)

    @property
    def display(self) -> Console:
        """Where the human-facing rendering goes.

        Stderr under `--json`: a progress display is about a command rather
        than being its output, and stdout has one document to carry.
        """
        return diagnostics if self.as_json else console

    def document(
        self,
        data: Mapping[str, object],
        *,
        ok: bool = True,
        errors: Iterable[Mapping[str, object]] = (),
    ) -> None:
        """The command's own result. A no-op unless `--json` was asked for."""
        if not self.as_json:
            return
        self._write(ok=ok, data=data, errors=list(errors))

    def failure(self, error: Exception) -> None:
        """The last thing a failing invocation prints, from `main()`.

        A command that already emitted its document reported its own partial
        state (PAR-5) and the exception is on its way out behind it; printing a
        second envelope would break the one-document contract.
        """
        if not self.as_json:
            print_error(str(error))
            remedy = getattr(error, "remedy", None)
            if remedy:
                diagnostics.print(f"  try: {remedy}", highlight=False, soft_wrap=True)
            return
        if self._emitted:
            return
        self._write(ok=False, data={}, errors=[from_error(error)])

    def _write(
        self,
        *,
        ok: bool,
        data: Mapping[str, object],
        errors: list[Mapping[str, object]],
    ) -> None:
        self._emitted = True
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "command": self.command,
                    "ok": ok,
                    "data": data,
                    "errors": errors,
                },
                indent=2,
            )
        )


_current = Output()


def begin(command: str, *, as_json: bool = False) -> Output:
    """Called first thing in a command body, before anything can fail.

    Anything raised earlier than this - a flag the parser rejects - is reported
    as text with exit code 2, because there is no command yet to name in an
    envelope.
    """
    global _current
    _current = Output(command, as_json)
    return _current


def current() -> Output:
    return _current
