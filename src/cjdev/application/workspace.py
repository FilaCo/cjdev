"""Finding the workspace a command was run inside.

A directory is a workspace if and only if it holds `.cjdev/`.
"""

from pathlib import Path

from cjdev.domain.layout import CJDEV_DIR
from cjdev.errors import PreconditionError


def find_root(start: Path) -> Path | None:
    """The nearest ancestor holding `.cjdev/`, or None.

    A walk rather than an exact match, so that commands work from inside a
    worktree the way git's own do. Workspaces may nest, and the nearest marker
    is the answer: an inner one shadows the outer for anything run inside it.
    """
    for candidate in (start, *start.parents):
        if (candidate / CJDEV_DIR).is_dir():
            return candidate
    return None


def require_root(start: Path) -> Path:
    root = find_root(start)
    if root is None:
        raise PreconditionError(
            f"no cjdev workspace found in {start} or any parent. "
            f"Create one with `cjdev init`."
        )
    return root
