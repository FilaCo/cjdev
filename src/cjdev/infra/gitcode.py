"""The GitCode API v5, and the token it is called with (ADR-0044).

The API is Gitee-style: the owner is in the path and the repository in the
body, and labels travel as one comma-separated string.
"""

import json
import os
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import final

from cjdev.domain.forge import FiledIssue, NewIssue, Repository
from cjdev.errors import ForgeError, PreconditionError

HOST = "gitcode.com"
API = "https://api.gitcode.com/api/v5"
TOKEN_VARIABLE = "GITCODE_TOKEN"
TIMEOUT = 30.0

Send = Callable[[str, str, Mapping[str, str], bytes], tuple[int, bytes]]
"""method, url, headers, body -> status, response body."""

Fill = Callable[[str], str | None]
"""host -> the password git's credential helpers hold for it."""


def issue_request(issue: NewIssue) -> tuple[str, dict[str, str]]:
    repository = _require_gitcode(issue.repository)
    payload = {"repo": repository.name, "title": issue.title, "body": issue.body}
    if issue.labels:
        payload["labels"] = ",".join(issue.labels)
    return f"{API}/repos/{repository.owner}/issues", payload


@final
class GitCodeForge:
    def __init__(self, token: Callable[[], str], send: Send | None = None) -> None:
        # A callable, so that a draft refused before sending never runs a
        # credential helper.
        self._token = token
        self._send = send or send_over_https

    def create_issue(self, issue: NewIssue) -> FiledIssue:
        url, payload = issue_request(issue)
        status, raw = self._send(
            "POST",
            url,
            {
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json.dumps(payload).encode(),
        )
        answer = _json(raw)
        if not 200 <= status < 300:
            message = answer.get("message") or raw.decode(errors="replace")[:200]
            raise ForgeError(f"GitCode answered {status}: {message}", status=status)
        if "html_url" not in answer:
            raise ForgeError(
                f"GitCode answered {status} with no issue in it: {raw[:200]!r}"
            )
        return FiledIssue(number=str(answer.get("number", "")), url=answer["html_url"])


@final
class DryRunForge:
    def __init__(self, emit: Callable[[str], None]) -> None:
        self._emit = emit

    def create_issue(self, issue: NewIssue) -> None:
        url, payload = issue_request(issue)
        # The body as Markdown rather than inside the JSON, where every
        # newline would read as `\n`.
        body = payload.pop("body")
        self._emit(f"POST {url}")
        for key, value in payload.items():
            self._emit(f"{key}: {value}")
        self._emit("")
        self._emit(body)


def find_token(host: str, *, environ: Mapping[str, str], fill: Fill) -> str:
    """`GITCODE_TOKEN`, then what git's credential helpers hold for the host.

    The variable first, because it is the one a caller sets on purpose; the
    helper is the token they already have, with no setup.
    """
    token = environ.get(TOKEN_VARIABLE, "").strip() or fill(host)
    if not token:
        raise PreconditionError(
            f"no {host} token: {TOKEN_VARIABLE} is unset, and git holds no "
            f"credential for https://{host}.",
            remedy=f"export {TOKEN_VARIABLE}=<a {host} access token>",
        )
    return token


def credential_fill(host: str) -> str | None:
    """The password from `git credential fill`, or None.

    Not through `Executor`: the answer is a secret, and the workspace log and
    `-v` record what a command printed. Every prompt is off, so a host with no
    stored credential is a None rather than a terminal or a GUI asking:
    git's own prompt via `GIT_TERMINAL_PROMPT`, askpass via an empty
    `GIT_ASKPASS` (which also overrides `SSH_ASKPASS`), and
    git-credential-manager via `GCM_INTERACTIVE`.
    """
    env = os.environ | {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "",
        "GCM_INTERACTIVE": "never",
    }
    try:
        done = subprocess.run(
            ["git", "credential", "fill"],
            input=f"protocol=https\nhost={host}\n\n",
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    except OSError:
        return None
    if done.returncode:
        return None
    for line in done.stdout.splitlines():
        key, _, value = line.partition("=")
        if key == "password" and value:
            return value
    return None


def send_over_https(
    method: str, url: str, headers: Mapping[str, str], body: bytes
) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url, data=body, headers=dict(headers), method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise ForgeError(f"cannot reach {url}: {reason}") from None


def _require_gitcode(repository: Repository) -> Repository:
    if repository.host != HOST:
        raise PreconditionError(
            f"{repository.url} is not on {HOST}, and GitCode is the only forge "
            f"cjdev speaks."
        )
    return repository


def _json(raw: bytes) -> dict:
    try:
        answer = json.loads(raw)
    except ValueError:
        return {}
    return answer if isinstance(answer, dict) else {}
