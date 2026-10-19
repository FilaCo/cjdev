"""What cjdev asks of a code forge, as data: a repository, an issue to file,
the issue it became, and an issue somebody else filed."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import final
from urllib.parse import urlsplit

from cjdev.domain.manifest import Project
from cjdev.errors import ManifestError, UsageError

DEFAULT_ISSUE_HOME = "cangjie_compiler"
"""The project a task's issue lives in when nothing says otherwise: the
default of `[forge] issue_home`, and the only place the name is written."""


@final
@dataclass(frozen=True)
class Repository:
    host: str
    owner: str
    name: str

    @property
    def url(self) -> str:
        return f"https://{self.host}/{self.owner}/{self.name}"


def parse_repository(url: str) -> Repository:
    """The forge repository behind a project's `upstream` URL.

    https only: an ssh remote names the same repository, but nothing in the
    manifest uses one, and guessing the web host from an ssh alias is how a
    request ends up at the wrong forge.
    """
    parts = urlsplit(url)
    path = parts.path.strip("/").removesuffix(".git").split("/")
    if parts.scheme != "https" or not parts.hostname or len(path) != 2 or "" in path:
        raise ManifestError(
            f"{url} is not an https://<host>/<owner>/<repository> URL, "
            f"so there is no forge repository to file against."
        )
    return Repository(host=parts.hostname, owner=path[0], name=path[1])


@final
@dataclass(frozen=True)
class NewIssue:
    repository: Repository
    title: str
    body: str
    labels: tuple[str, ...] = ()


@final
@dataclass(frozen=True)
class FiledIssue:
    number: str
    """A string, whatever JSON type the forge sends: it is only ever shown,
    and Gitee-style APIs are not consistent about it."""
    url: str


@final
@dataclass(frozen=True)
class IssueRef:
    repository: Repository
    number: str

    @property
    def url(self) -> str:
        return f"{self.repository.url}/issues/{self.number}"


@final
@dataclass(frozen=True)
class Issue:
    ref: IssueRef
    title: str


def parse_issue_url(url: str) -> IssueRef:
    """`https://<host>/<owner>/<repository>/issues/<n>`, the page a person
    copies from the browser."""
    parts = urlsplit(url.strip())
    path = parts.path.strip("/").split("/")
    if (
        parts.scheme != "https"
        or not parts.hostname
        or len(path) != 4
        or path[2] != "issues"
        or not path[3].isdigit()
        or "" in path
    ):
        raise UsageError(
            f"{url} is not an https://<host>/<owner>/<repository>/issues/<n> URL."
        )
    return IssueRef(Repository(parts.hostname, path[0], path[1]), path[3])


def home_of(ref: IssueRef, projects: Iterable[Project]) -> str:
    """The project whose upstream the issue is filed against."""
    for project in projects:
        try:
            if parse_repository(project.upstream_url) == ref.repository:
                return project.name
        except ManifestError:
            continue
    raise UsageError(
        f"{ref.url} is filed against {ref.repository.url}, which is no "
        f"project's upstream."
    )
