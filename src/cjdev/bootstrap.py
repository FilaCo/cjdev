"""The composition root: the one place that knows which concrete thing is which.

Everything above it receives its collaborators; nothing above it constructs
one. Kept out of `cli/` so that a test, and later a CI entry point, can
assemble the same graph without going through Typer.
"""

import sys
from collections.abc import Callable
from functools import cached_property
from typing import final

from cjdev.application.clean_workspace import CleanWorkspace
from cjdev.application.init_workspace import InitWorkspace
from cjdev.application.ports import Executor, FileSystem, Prompt
from cjdev.application.report_status import ReportStatus
from cjdev.domain.manifest import Manifest
from cjdev.infra.config import load_bundled_manifest, render_workspace_config
from cjdev.infra.executor import build_executor
from cjdev.infra.filesystem import build_file_system
from cjdev.infra.git import (
    list_worktrees,
    provision_object_store,
    read_checkouts,
    remove_object_store,
)
from cjdev.infra.prompt import InteractivePrompt, NonInteractivePrompt


@final
class Container:
    def __init__(self, emit: Callable[[str], None] = print) -> None:
        self.emit = emit
        """Where captured command output goes. Public and settable because a
        command only learns where its output should be collected once it has
        built the display that collects it; the composition root is the right
        place for that knot, and the only one."""

    @cached_property
    def manifest(self) -> Manifest:
        """The default project set. Workspace overrides land here (CFG-2)."""
        return load_bundled_manifest()

    def executor(self, *, dry_run: bool = False, verbose: bool = False) -> Executor:
        return build_executor(dry_run=dry_run, verbose=verbose, emit=self.emit)

    def file_system(self, *, dry_run: bool = False) -> FileSystem:
        return build_file_system(dry_run=dry_run, emit=self.emit)

    def prompt(self, *, interactive: bool = True, assume_yes: bool = False) -> Prompt:
        """`interactive` and `assume_yes` are separate because they answer
        different questions: one supplies settings, the other supplies consent
        to a destructive action (UX-2, UX-10). A pipe forces the first; only
        `--yes` supplies the second.
        """
        if interactive and not assume_yes and sys.stdin.isatty():
            return InteractivePrompt()
        return NonInteractivePrompt(assume_yes=assume_yes)

    def init_workspace(
        self,
        *,
        dry_run: bool = False,
        verbose: bool = False,
        defaults: bool = False,
    ) -> InitWorkspace:
        return InitWorkspace(
            manifest=self.manifest,
            executor=self.executor(dry_run=dry_run, verbose=verbose),
            file_system=self.file_system(dry_run=dry_run),
            # A dry run answers its own questions: it changes nothing, so a
            # wizard would only stand between the user and the plan.
            prompt=self.prompt(interactive=not (defaults or dry_run)),
            provision=provision_object_store,
            remove=remove_object_store,
            render_config=render_workspace_config,
        )

    def report_status(self, *, verbose: bool = False) -> ReportStatus:
        """No `FileSystem` and no `Prompt`: it changes nothing, so there is
        nothing to make dry, and nothing to ask permission for."""
        return ReportStatus(
            manifest=self.manifest,
            executor=self.executor(verbose=verbose),
            read_checkouts=read_checkouts,
        )

    def clean_workspace(
        self, *, dry_run: bool = False, verbose: bool = False, assume_yes: bool = False
    ) -> CleanWorkspace:
        return CleanWorkspace(
            executor=self.executor(dry_run=dry_run, verbose=verbose),
            file_system=self.file_system(dry_run=dry_run),
            # A dry run removes nothing, so there is nothing to consent to.
            prompt=self.prompt(
                interactive=not dry_run, assume_yes=assume_yes or dry_run
            ),
            list_worktrees=list_worktrees,
        )
