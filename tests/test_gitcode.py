"""The GitCode client and its token. Nothing here reaches the network: the
transport and the credential helper are fakes, or a real git with a helper
that is a shell function."""

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

from cjdev.domain.forge import NewIssue, Repository, parse_repository
from cjdev.errors import ForgeError, ManifestError, PreconditionError
from cjdev.infra.gitcode import (
    DryRunForge,
    GitCodeForge,
    credential_fill,
    find_token,
)

COMPILER = Repository("gitcode.com", "Cangjie", "cangjie_compiler")
ISSUE = NewIssue(COMPILER, "[Bug]: x", "### What\n\nIt crashes.\n", ("bug", "sema"))


class FakeSend:
    def __init__(self, status: int = 200, answer: object = None) -> None:
        self.sent: list[tuple[str, str, Mapping[str, str], dict]] = []
        self._status = status
        self._answer = (
            answer
            if answer is not None
            else {
                "number": 1185,
                "html_url": "https://gitcode.com/Cangjie/cangjie_compiler/issues/1185",
            }
        )

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes
    ) -> tuple[int, bytes]:
        self.sent.append((method, url, headers, json.loads(body)))
        return self._status, json.dumps(self._answer).encode()


class TestTheRepository:
    def test_it_comes_from_the_upstream_url(self):
        # Act / Assert
        assert (
            parse_repository("https://gitcode.com/Cangjie/cangjie_compiler.git")
            == COMPILER
        )

    def test_an_ssh_remote_is_refused_rather_than_guessed_at(self):
        # Act / Assert
        with pytest.raises(ManifestError):
            parse_repository("git@gitcode.com:Cangjie/cangjie_compiler.git")


class TestCreatingAnIssue:
    def test_owner_in_the_path_repository_in_the_body(self):
        # Arrange
        send = FakeSend()

        # Act
        GitCodeForge(lambda: "tok", send).create_issue(ISSUE)

        # Assert: the Gitee-style shape, verified by hand against GitCode.
        method, url, _, payload = send.sent[0]
        assert method == "POST"
        assert url == "https://api.gitcode.com/api/v5/repos/Cangjie/issues"
        assert payload["repo"] == "cangjie_compiler"
        assert payload["title"] == "[Bug]: x"
        assert payload["body"] == ISSUE.body

    def test_labels_travel_as_one_comma_separated_string(self):
        # Arrange
        send = FakeSend()

        # Act
        GitCodeForge(lambda: "tok", send).create_issue(ISSUE)

        # Assert
        assert send.sent[0][3]["labels"] == "bug,sema"

    def test_the_token_is_a_bearer_header(self):
        # Arrange
        send = FakeSend()

        # Act
        GitCodeForge(lambda: "tok", send).create_issue(ISSUE)

        # Assert
        assert send.sent[0][2]["Authorization"] == "Bearer tok"

    def test_it_answers_with_the_number_and_the_url(self):
        # Act
        filed = GitCodeForge(lambda: "tok", FakeSend()).create_issue(ISSUE)

        # Assert
        assert filed.number == "1185"
        assert filed.url.endswith("/issues/1185")

    def test_a_refusal_carries_the_status_and_the_forge_s_message(self):
        # Arrange
        send = FakeSend(401, {"message": "invalid token"})

        # Act / Assert
        with pytest.raises(ForgeError, match="401: invalid token") as refusal:
            GitCodeForge(lambda: "tok", send).create_issue(ISSUE)
        assert refusal.value.details() == {"status": 401}

    def test_another_forge_is_refused_before_anything_is_sent(self):
        # Arrange
        send = FakeSend()
        elsewhere = NewIssue(Repository("github.com", "a", "b"), "t", "b")

        # Act / Assert
        with pytest.raises(PreconditionError, match=r"not on gitcode\.com"):
            GitCodeForge(lambda: "tok", send).create_issue(elsewhere)
        assert send.sent == []


class TestADryRun:
    def test_it_prints_the_request_and_the_body_and_files_nothing(self):
        # Arrange
        lines: list[str] = []

        # Act
        filed = DryRunForge(lines.append).create_issue(ISSUE)

        # Assert
        assert filed is None
        assert lines[0] == "POST https://api.gitcode.com/api/v5/repos/Cangjie/issues"
        assert "labels: bug,sema" in lines
        assert lines[-1] == ISSUE.body


class TestTheToken:
    def test_the_variable_wins_over_the_credential_helper(self):
        # Act: the variable is the one a caller sets on purpose.
        token = find_token(
            "gitcode.com", environ={"GITCODE_TOKEN": "env"}, fill=lambda _: "git"
        )

        # Assert
        assert token == "env"

    def test_without_it_the_credential_helper_answers(self):
        # Act
        token = find_token("gitcode.com", environ={}, fill=lambda _: "git")

        # Assert
        assert token == "git"

    def test_with_neither_the_refusal_names_the_variable(self):
        # Act / Assert
        with pytest.raises(PreconditionError) as refusal:
            find_token("gitcode.com", environ={}, fill=lambda _: None)
        assert refusal.value.remedy is not None
        assert "GITCODE_TOKEN" in refusal.value.remedy


@pytest.mark.usefixtures("git_available")
class TestGitCredentialFill:
    @pytest.fixture
    def isolated(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        config = tmp_path / "gitconfig"
        config.write_text("")
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        monkeypatch.chdir(tmp_path)
        return config

    def test_it_reads_the_password_the_helper_holds(self, isolated: Path):
        # Arrange
        subprocess.run(
            [
                "git",
                "config",
                "--file",
                str(isolated),
                "credential.helper",
                "!f() { echo username=me; echo password=from-helper; }; f",
            ],
            check=True,
        )

        # Act / Assert
        assert credential_fill("gitcode.com") == "from-helper"

    def test_no_credential_is_none_rather_than_a_prompt(
        self, isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange: an askpass that would answer if git were allowed to ask.
        askpass = tmp_path / "askpass"
        askpass.write_text("#!/bin/sh\necho asked\n")
        askpass.chmod(0o755)
        monkeypatch.setenv("SSH_ASKPASS", str(askpass))

        # Act / Assert
        assert credential_fill("gitcode.com") is None
