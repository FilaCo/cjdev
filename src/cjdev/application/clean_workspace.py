"""Removing a workspace: the inverse of `init`.
Everything *inside* the workspace root goes, branch-set worktrees included.
The root directory itself is left standing.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import final

from cjdev.application.ports import Executor, FileSystem, Prompt
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import AbortedError, PreconditionError

ListWorktrees = Callable[[Executor, Path], tuple[str, ...]]


@final
@dataclass(frozen=True)
class CleanPlan:
    root: Path
    entries: tuple[Path, ...]
    """Everything directly inside the root, which is what will be removed."""
    projects: tuple[str, ...]
    stray_worktrees: tuple[str, ...]
    """Checkouts linked to these stores from *outside* the workspace root.

    Ones inside it are deleted along with everything else; ones outside would
    be left pointing at a store that no longer exists (R9). `cjdev` never
    creates those, so finding any means something else did.
    """


@final
class CleanWorkspace:
    def __init__(
        self,
        executor: Executor,
        file_system: FileSystem,
        prompt: Prompt,
        list_worktrees: ListWorktrees,
    ) -> None:
        self._executor = executor
        self._fs = file_system
        self._prompt = prompt
        self._list_worktrees = list_worktrees

    def plan(self, root: Path) -> CleanPlan:
        layout = WorkspaceLayout(root)
        # Read off the disk rather than off the manifest: what a workspace
        # holds is what was fetched into it, and a manifest that has since
        # gained or lost a project would otherwise make `clean` miss stores or
        # invent ones (CFG-10).
        bare = Path(layout.bare_dir)
        provisioned = (
            [
                (store.name.removesuffix(".git"), store)
                for store in sorted(bare.iterdir())
                if store.is_dir()
            ]
            if bare.is_dir()
            else []
        )
        return CleanPlan(
            root=root,
            entries=tuple(sorted(root.iterdir())),
            projects=tuple(name for name, _ in provisioned),
            stray_worktrees=tuple(
                path
                for _, store in provisioned
                for path in self._list_worktrees(self._executor, store)
                if not _inside(path, root)
            ),
        )

    def perform(self, root: Path, *, force: bool = False) -> CleanPlan:
        plan = self.plan(root)
        if plan.stray_worktrees and not force:
            raise PreconditionError(
                f"{len(plan.stray_worktrees)} worktree(s) outside this workspace "
                f"still use it: {', '.join(plan.stray_worktrees)}. Remove them "
                f"first, or pass --force to delete the stores out from under them."
            )
        question = (
            f"Delete everything in {plan.root}, including the objects fetched "
            f"into {len(plan.projects)} project(s)?"
        )
        if not self._prompt.confirm(question, destructive=True):
            raise AbortedError("clean")

        for entry in plan.entries:
            self._fs.remove(entry)
        return plan


def _inside(path: str, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True
