"""Consent and settings are different questions."""

import tempfile
from pathlib import Path

import pytest

from cjdev.errors import AbortedError, InputRequiredError, PreconditionError
from cjdev.infra.prompt import InteractivePrompt, NonInteractivePrompt


class TestWithoutATerminal:
    def test_a_destructive_action_is_refused_rather_than_assumed(self):
        # "Never destructive by default", in the case where nobody is
        # there to answer. Silence is not consent.
        prompt = NonInteractivePrompt(assume_yes=False)

        with pytest.raises(InputRequiredError) as refusal:
            prompt.confirm("Delete every worktree?", destructive=True)

        # The remedy is a field rather than a sentence in the message: the
        # caller this refusal exists for re-runs the command, and reads what
        # to change from the envelope rather than by parsing prose.
        assert refusal.value.remedy == "run it in a terminal"

    def test_an_answer_given_up_front_is_the_consent_a_terminal_would_have(self):
        assert NonInteractivePrompt(assume_yes=True).confirm("Delete?")

    def test_a_harmless_question_proceeds_unanswered(self):
        # Otherwise every CI script that runs `init` would need consent it has
        # no way to give, and whatever gave it would also arm the deletions.
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


class TestTheEditor:
    @pytest.fixture(autouse=True)
    def _drafts_in_tmp_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    def test_it_returns_what_the_editor_saved(self, monkeypatch: pytest.MonkeyPatch):
        # Arrange: VISUAL is split like a shell would, flags and all.
        monkeypatch.setenv("VISUAL", "sh -c 'echo filled >> \"$1\"' sh")

        # Act
        edited = InteractivePrompt().edit("draft\n", remedy="")

        # Assert
        assert edited == "draft\nfilled\n"

    def test_a_failing_editor_keeps_the_draft_and_says_where(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        monkeypatch.setenv("VISUAL", "false")

        # Act / Assert
        with pytest.raises(AbortedError, match="the draft is in") as refusal:
            InteractivePrompt().edit("draft\n", remedy="")
        kept = str(refusal.value).split("the draft is in ")[1].split(":")[0]
        assert Path(kept).read_text() == "draft\n"

    def test_without_a_terminal_the_remedy_is_the_caller_s(self):
        # Act / Assert
        with pytest.raises(InputRequiredError) as refusal:
            NonInteractivePrompt(assume_yes=True).edit("", remedy="pass --body-file")
        assert refusal.value.remedy == "pass --body-file"
