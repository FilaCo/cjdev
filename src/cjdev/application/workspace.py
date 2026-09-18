"""Finding the workspace a command was run inside, and what it holds.

A directory is a workspace if and only if it holds `.cjdev/`, and a workspace
holds the projects its object stores say it holds.
"""

from collections.abc import Iterable
from pathlib import Path

from cjdev.domain.layout import CJDEV_DIR, WorkspaceLayout
from cjdev.domain.manifest import Manifest
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


def require_branch_set(root: Path, cwd: Path) -> str:
    """The branch set the caller is standing in.

    The directory name rather than the branch read back from git: flattening is
    idempotent, so the two produce the same paths, and a build has no reason to
    run six `git` invocations to learn a label.
    """
    for directory in (cwd, *cwd.parents):
        if directory == root:
            break
        if directory.parent == root:
            return directory.name
    raise PreconditionError(
        f"{cwd} is not inside a branch set of {root}, so there is nothing to build.",
        remedy="cd into a branch set",
    )


def held_projects(layout: WorkspaceLayout, manifest: Manifest) -> tuple[str, ...]:
    """The projects this workspace actually holds, in manifest order.

    Read off the disk rather than off the manifest, because a workspace's
    project set is what its object stores say it is. A store the manifest has
    since stopped listing is still one of them: hiding a directory full of
    fetched objects because a config no longer mentions it is how a report
    becomes a thing you cannot trust.
    """
    bare = Path(layout.bare_dir)
    if not bare.is_dir():
        return ()
    return in_manifest_order(
        manifest,
        (store.name.removesuffix(".git") for store in bare.iterdir() if store.is_dir()),
    )


def in_manifest_order(manifest: Manifest, names: Iterable[str]) -> tuple[str, ...]:
    """Manifest order first, then whatever the manifest has never heard of.

    Manifest order is the tie-break for every ordering cjdev produces, so that
    output cannot depend on scheduling. A store the manifest has no opinion
    about still has to be ordered by something, and its name is the only
    stable thing left.
    """
    known = tuple(project.name for project in manifest.projects)
    remaining = set(names)
    return tuple(
        [name for name in known if name in remaining]
        + sorted(remaining.difference(known))
    )
