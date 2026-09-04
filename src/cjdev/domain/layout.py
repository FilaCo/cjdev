"""The workspace tree of §4.1, as pure path algebra over a root.

Every path `cjdev` reads or writes is derived here and nowhere else. Two
requirements depend on that being true rather than merely tidy: the shared
ccache only hits across worktrees if the layout is stable and the workspace
root is a single known prefix (CACHE-2, R3), and everything `cjdev` owns has
to sit under one root so that `rm -rf` is a complete uninstall (CFG-6).

The tree is split by audience. The root holds the branch sets, because those
are what a person `cd`s into and works in. Everything else the tool owns -
object stores, build directories, caches, logs and the workspace config -
lives under `.cjdev/`, which is also what marks the directory as a workspace
(CFG-7).

No filesystem access happens here. `PurePath` rather than `Path` is what makes
that a checked fact rather than a promise: it has no `mkdir`, no `exists`, no
`read_text`, so `ty` rejects I/O in this module instead of a reviewer having
to notice it. Callers that need to touch a path wrap it in `Path(...)`, which
is the boundary crossing made visible.
"""

from dataclasses import dataclass
from pathlib import PurePath
from typing import final

from cjdev.errors import UsageError

CJDEV_DIR = ".cjdev"
"""Everything the tool owns, and the workspace marker (CFG-7)."""

WORKSPACE_CONFIG = "config.toml"
"""Inside the marker: workspace config and manifest overrides (CFG-1/2).

An ordinary file the user may open and edit; `cjdev config` is convenience on
top of it, not the only way in.
"""


def flatten_branch_set(name: str) -> str:
    """The directory name a branch set gets in the workspace root.

    Only `/` is rewritten, because on Linux it is the one character a git
    branch name may contain and a filename may not. Everything else survives,
    so the directory stays recognisable as the branch it holds.

    **The mapping is one-way**: `fix/parser-ice` and `fix-parser-ice` flatten
    to the same directory. The branch in git therefore remains the identity of
    a branch set, and this is a label derived from it - which is why the real
    name is read back with `git worktree list` rather than from the directory,
    and why creating a branch set must refuse a name that collides with an
    existing one (BRANCH-1).
    """
    return _checked_branch_set(name).replace("/", "-")


def _checked_branch_set(name: str) -> str:
    if not name:
        raise UsageError("branch set name must not be empty.")
    if name.startswith("/") or name.endswith("/"):
        raise UsageError(
            f"branch set name must not start or end with '/', got {name!r}."
        )
    for component in name.split("/"):
        # git's own rule (`git check-ref-format`), which also happens to
        # exclude '.', '..' and anything that could escape the workspace root.
        if not component or component.startswith("."):
            raise UsageError(
                f"branch set name components must be non-empty and must not "
                f"start with '.', got {name!r}."
            )
    return name


@final
@dataclass(frozen=True)
class WorkspaceLayout:
    root: PurePath

    @property
    def marker(self) -> PurePath:
        """Its existence is what makes a directory a workspace (CFG-7)."""
        return self.root / CJDEV_DIR

    @property
    def config_file(self) -> PurePath:
        return self.marker / WORKSPACE_CONFIG

    @property
    def bare_dir(self) -> PurePath:
        return self.marker / "bare"

    @property
    def cache_dir(self) -> PurePath:
        return self.marker / "cache"

    @property
    def ccache_dir(self) -> PurePath:
        """One store for every branch set and every environment mode.

        Shared on purpose (CACHE-1) and mounted into containers at this same
        path so host and container builds hit each other's objects (CACHE-3).
        """
        return self.cache_dir / "ccache"

    @property
    def misc_cache_dir(self) -> PurePath:
        return self.cache_dir / "misc"

    def object_store(self, project: str) -> PurePath:
        """The bare repository backing every worktree of this project.

        One store per project, cloned and fetched once (§7 decision 1).
        """
        return self.bare_dir / f"{self._segment(project, 'project')}.git"

    def branch_set_dir(self, branch_set: str) -> PurePath:
        """One flat directory in the workspace root, holding its worktrees.

        Flat and at the root because this is the only path a person types.
        """
        return self.root / flatten_branch_set(branch_set)

    def worktree(self, branch_set: str, project: str) -> PurePath:
        return self.branch_set_dir(branch_set) / self._segment(project, "project")

    def build_dir(self, branch_set: str, profile: str, unit: str) -> PurePath:
        """Out-of-tree, and keyed by branch set x profile x unit (BUILD-5).

        Two branch sets never share a build directory; that is what makes
        switching cheap enough to be worth doing (NFR-6).
        """
        return (
            self.marker
            / "build"
            / flatten_branch_set(branch_set)
            / self._segment(profile, "profile")
            / self._segment(unit, "build unit")
        )

    def dist_dir(self, branch_set: str, profile: str) -> PurePath:
        """The assembled SDK - the install target of every `build.py`."""
        return (
            self.marker
            / "dist"
            / flatten_branch_set(branch_set)
            / self._segment(profile, "profile")
        )

    def log_dir(self, branch_set: str) -> PurePath:
        """One directory per branch set; one file per unit of work.

        Per-unit files rather than one shared log, so that a fan-out does not
        interleave on disk any more than it does on screen (PAR-11, UX-3).
        """
        return self.marker / "log" / flatten_branch_set(branch_set)

    @staticmethod
    def _relative(name: str, what: str) -> PurePath:
        if not name:
            raise UsageError(f"{what} name must not be empty.")
        candidate = PurePath(name)
        if candidate.is_absolute():
            raise UsageError(f"{what} name must be relative, got {name!r}.")
        # `Path` folds `.` away entirely, so a name of "." arrives here with no
        # parts at all and would otherwise resolve to the parent directory.
        if not candidate.parts or any(
            part in ("", ".", "..") for part in candidate.parts
        ):
            raise UsageError(
                f"{what} name must not contain '.' or '..' segments, got {name!r}."
            )
        return candidate

    @classmethod
    def _segment(cls, name: str, what: str) -> str:
        checked = cls._relative(name, what)
        if len(checked.parts) != 1:
            raise UsageError(
                f"{what} name must be a single path segment, got {name!r}."
            )
        return checked.parts[0]
