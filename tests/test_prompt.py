"""Consent and settings are different questions."""

import pytest

from cjdev.errors import PreconditionError
from cjdev.infra.prompt import NonInteractivePrompt


class TestWithoutATerminal:
    def test_a_destructive_action_is_refused_rather_than_assumed(self):
        # "Never destructive by default", in the case where nobody is
        # there to answer. Silence is not consent.
        prompt = NonInteractivePrompt(assume_yes=False)

        with pytest.raises(PreconditionError, match="--yes"):
            prompt.confirm("Delete every worktree?", destructive=True)

    def test_yes_supplies_the_consent_a_terminal_would_have(self):
        assert NonInteractivePrompt(assume_yes=True).confirm("Delete?")

    def test_a_harmless_question_proceeds_without_yes(self):
        # Otherwise every CI script that runs `init` would need --yes, which
        # would then also be the flag that arms deletions.
        prompt = NonInteractivePrompt(assume_yes=False)

        assert prompt.confirm("Create a workspace?", destructive=False)

    def test_confirm_defaults_to_treating_a_question_as_destructive(self):
        with pytest.raises(PreconditionError):
            NonInteractivePrompt(assume_yes=False).confirm("Unclassified?")


class TestChoosing:
    def test_the_preselection_is_the_answer(self):
        chosen = NonInteractivePrompt(assume_yes=False).choose(
            "Projects", ["a", "b", "c"], preselected=["a", "c"]
        )

        assert chosen == ("a", "c")

    def test_the_answer_keeps_manifest_order(self):
        # Everything downstream orders by this, so it may not come
        # back in the order the answer happened to arrive in.
        chosen = NonInteractivePrompt(assume_yes=False).choose(
            "Projects", ["a", "b", "c"], preselected=["c", "a"]
        )

        assert chosen == ("a", "c")
