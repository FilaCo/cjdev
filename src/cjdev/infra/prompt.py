"""Asking, or declining to ask, through `questionary`."""

from collections.abc import Sequence
from typing import final

import questionary

from cjdev.errors import AbortedError, InputRequiredError


@final
class InteractivePrompt:
    def confirm(self, question: str, *, destructive: bool = True) -> bool:
        answer = questionary.confirm(question, default=not destructive).ask()
        if answer is None:
            # `ask()` returns None on Ctrl-C. Treating that as "no" would be
            # defensible for a confirmation and wrong for anything else, so it
            # is an abort rather than an answer.
            raise AbortedError(question)
        return bool(answer)

    def choose(
        self, question: str, options: Sequence[str], *, preselected: Sequence[str]
    ) -> tuple[str, ...]:
        chosen = questionary.checkbox(
            question,
            choices=[
                questionary.Choice(option, checked=option in preselected)
                for option in options
            ],
        ).ask()
        if chosen is None:
            raise AbortedError(question)
        # Re-ordered to match `options`, because that is manifest order and
        # everything downstream depends on it being stable.
        return tuple(option for option in options if option in set(chosen))


@final
class NonInteractivePrompt:
    """No terminal, or `--yes`, or `--dry-run`.

    Silence is not consent for a destructive action: without `--yes` those
    refuse rather than proceed, which is "never destructive by default" in
    the case where nobody is there to answer.
    """

    def __init__(self, *, assume_yes: bool) -> None:
        self._assume_yes = assume_yes

    def confirm(self, question: str, *, destructive: bool = True) -> bool:
        if self._assume_yes or not destructive:
            return True
        # Named as a flag rather than described in prose, because the caller
        # this refusal exists for cannot read prose: it re-runs the command,
        # and the only way it learns what to add is this field (UX-14).
        raise InputRequiredError(
            f"{question}\n  Refusing a destructive action with no terminal to ask at.",
            remedy="re-run with --yes",
        )

    def choose(
        self,
        question: str,  # noqa: ARG002
        options: Sequence[str],
        *,
        preselected: Sequence[str],
    ) -> tuple[str, ...]:
        return tuple(option for option in options if option in set(preselected))
