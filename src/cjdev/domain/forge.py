"""What cjdev asks of a code forge, as data: a repository, an issue to file,
and the issue it became."""

from dataclasses import dataclass
from typing import final
from urllib.parse import urlsplit

from cjdev.errors import ManifestError


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
