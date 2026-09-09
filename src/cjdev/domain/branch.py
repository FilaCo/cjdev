"""Whether a string may be a git branch name.

A branch set is identified by the branch it holds, so one check answers both
questions: whether git will accept the ref, and whether the directory derived
from it stays inside the workspace. The rules are `git check-ref-format`'s,
and the suite cross-checks them against the binary rather than against our
reading of the manual.
"""

from cjdev.errors import UsageError

FORBIDDEN = " ~^:?*[\\"
"""Characters git refuses anywhere in a ref, plus the space.

`\\` is here because git rejects it outright rather than because Windows would:
a ref is not a path, and treating it as one is how a name that is legal on one
machine stops being legal on another.
"""


def check_branch_name(name: str) -> str:
    """The name back, or a `UsageError` saying what is wrong with it.

    Applied before anything is created. A name refused by the fifth project's
    `worktree add` would leave four checkouts and four branches to take back,
    and the taking back is the part that can fail.
    """
    if not name:
        raise UsageError("branch name must not be empty.")
    if name.startswith("/") or name.endswith("/"):
        raise UsageError(f"branch name must not start or end with '/', got {name!r}.")

    for part in name.split("/"):
        # Checked before the rest so that `..` is reported as the rule it
        # breaks here: that part is also the one that could escape the root.
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
        # git's own ref rules allow it; every command that takes a branch
        # where an option could go does not.
        raise UsageError(f"branch name must not start with '-', got {name!r}.")
    return name
