"""Whether a string may be a git branch name.

`git check-ref-format`'s rules, cross-checked against the binary in the suite.
One check for two questions: whether git accepts the ref, and whether the
directory derived from it stays inside the workspace.
"""

from cjdev.errors import UsageError

FORBIDDEN = " ~^:?*[\\"
"""Characters git refuses anywhere in a ref, plus the space."""


def check_branch_name(name: str) -> str:
    """The name back, or a `UsageError` saying what is wrong with it."""
    if not name:
        raise UsageError("branch name must not be empty.")
    if name.startswith("/") or name.endswith("/"):
        raise UsageError(f"branch name must not start or end with '/', got {name!r}.")

    for part in name.split("/"):
        # First, so that `..` is reported as the leading dot it is - that part
        # is also the one that could escape the root.
        if not part:
            raise UsageError(f"branch name must not have an empty part, got {name!r}.")
        if part.startswith("."):
            raise UsageError(
                f"branch name parts must not start with '.', got {name!r}."
            )
        if part.endswith(".lock"):
            raise UsageError(
                f"branch name parts must not end with '.lock', got {name!r}."
            )

    for char in name:
        if char in FORBIDDEN or ord(char) < 0x20 or ord(char) == 0x7F:
            raise UsageError(f"branch name must not contain {char!r}, got {name!r}.")

    if ".." in name or "@{" in name or name == "@":
        raise UsageError(f"branch name must not contain '..' or '@{{', got {name!r}.")
    if name.endswith("."):
        raise UsageError(f"branch name must not end with '.', got {name!r}.")
    if name.startswith("-"):
        # git's ref rules allow it; every command that takes a branch where an
        # option could go does not.
        raise UsageError(f"branch name must not start with '-', got {name!r}.")
    return name
