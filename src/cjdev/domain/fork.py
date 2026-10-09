"""The user's fork of a project, derived from its upstream URL and an owner.

Derived rather than stored: the owner is one workspace setting, and the URL of
every project's fork follows from it, so a per-project list would be six
copies of one fact (ADR-0043).
"""

import re

from cjdev.errors import PreconditionError, UsageError

_OWNER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
"""What a namespace on a forge may look like. Stricter than any one forge,
because the owner is spliced into a URL and anything else would change which
host or path it names."""

_SCP = re.compile(r"(?P<head>[^/:@]+@[^/:]+:)(?P<path>.+)")
"""`git@host:owner/repo.git` - git's scp-like form, which has no scheme."""


def check_fork_owner(owner: str) -> str:
    if not _OWNER.fullmatch(owner):
        raise UsageError(
            f"{owner!r} is not a fork owner: expected a user or group name, "
            f"letters, digits, '.', '_' or '-'."
        )
    return owner


def fork_url(upstream_url: str, owner: str) -> str:
    """`upstream_url` with its namespace replaced by `owner`.

    Only the segment right before the repository is replaced: a fork lands
    in the owner's own namespace, and the forges cjdev talks to have no
    subgroups in the paths it ships.
    """
    check_fork_owner(owner)
    prefix, path = _split(upstream_url)
    namespace, separator, repository = path.rstrip("/").rpartition("/")
    if not separator or not namespace.strip("/"):
        raise PreconditionError(
            f"cannot derive a fork from {upstream_url}: it has no namespace "
            f"before the repository to replace."
        )
    parent, slash, _ = namespace.rpartition("/")
    return f"{prefix}{parent}{slash}{owner}/{repository}"


def web_page(remote_url: str) -> str | None:
    """The page a browser opens for a repository, or None when the URL names
    no web host - a `file://` remote, say."""
    scp = _SCP.fullmatch(remote_url)
    if scp:
        host = scp["head"].partition("@")[2].rstrip(":")
        url = f"https://{host}/{scp['path']}"
    elif remote_url.startswith(("https://", "http://")):
        url = remote_url
    else:
        return None
    return url.rstrip("/").removesuffix(".git")


def _split(url: str) -> tuple[str, str]:
    """The part that names the host, and the path after it."""
    scp = _SCP.fullmatch(url)
    if scp:
        return scp["head"], scp["path"]
    scheme, separator, rest = url.partition("://")
    if not separator:
        raise PreconditionError(
            f"cannot derive a fork from {url}: not a URL git can push to."
        )
    host, slash, path = rest.partition("/")
    return f"{scheme}://{host}", f"{slash}{path}"
