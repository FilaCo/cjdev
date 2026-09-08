"""The composition root: the one place that knows which concrete thing is which.

Everything above it receives its collaborators; nothing above it constructs
one. Kept out of `cli/` so that a test, and later a CI entry point, can
assemble the same graph without going through Typer.
"""

import sys
from collections.abc import Callable, Sequence
from functools import cached_property
from pathlib import Path
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
from cjdev.infra.journal import CommandJournal, open_journal
from cjdev.infra.prompt import InteractivePrompt, NonInteractivePrompt


def _ignore(_: str) -> None:
    pass


@final
class Container:
    def __init__(self, emit: Callable[[str], None] = print) -> None:
        self.emit = emit
        """Where captured command output goes. Public and settable because a
        command only learns where its output should be collected once it has
        built the display that collects it; the composition root is the right
        place for that knot, and the only one."""

        self.report_step: Callable[[str], None] = _ignore
        """What the running command is doing, for the live display. Settable
        for the same reason as `emit`, and separately from it, because one is
        a transcript kept for later and the other is a label overwritten a
        second after it is drawn."""

        self._journal: CommandJournal | None = None
        self._journal_root: Path | None = None

    @cached_property
    def manifest(self) -> Manifest:
        """The default project set. Workspace overrides land here."""
        return load_bundled_manifest()

    def journal(self, root: Path, argv: Sequence[str]) -> CommandJournal:
        """Start recording this invocation into the workspace's own log.

        Every executor built afterwards writes to it, which is why a command
        opens this before it builds its use case. Read-only commands do not:
        a `status` run from a shell prompt would otherwise be most of the log.
        """
        self._journal = open_journal(root, argv)
        self._journal_root = root
        return self._journal

    def executor(self, *, dry_run: bool = False, verbose: bool = False) -> Executor:
        return build_executor(
            dry_run=dry_run,
            verbose=verbose,
            emit=self.emit,
            # A dry run runs no mutating command, so there is nothing that
            # happened for the log to record.
            record=None if dry_run or self._journal is None else self._journal.write,
            record_base=self._journal_root,
            report_step=self.report_step,
        )

    def file_system(self, *, dry_run: bool = False) -> FileSystem:
        return build_file_system(dry_run=dry_run, emit=self.emit)

    def prompt(self, *, interactive: bool = True, assume_yes: bool = False) -> Prompt:
        """`interactive` is whether to ask; `assume_yes` is the answer to give
        when nobody is asked.

        They are kept apart here rather than folded together, because consent
        and settings are different questions: a command whose only question is
        its confirmation may pass `interactive=False` on `--yes`, but a command
        with a wizard as well must not, or `--yes` would silently answer the
        wizard too.
        """
        if interactive and sys.stdin.isatty():
            return InteractivePrompt()
        return NonInteractivePrompt(assume_yes=assume_yes)

    def init_workspace(
        self, *, dry_run: bool = False, verbose: bool = False
    ) -> InitWorkspace:
        return InitWorkspace(
            manifest=self.manifest,
            executor=self.executor(dry_run=dry_run, verbose=verbose),
            file_system=self.file_system(dry_run=dry_run),
            # A dry run answers its own questions: it changes nothing, so a
            # wizard would only stand between the user and the plan, and a
            # plan that happens to include a removal still has nothing to ask
            # consent for.
            prompt=self.prompt(interactive=not dry_run, assume_yes=dry_run),
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
        self,
        *,
        dry_run: bool = False,
        verbose: bool = False,
        assume_yes: bool = False,
        interactive: bool = True,
    ) -> CleanWorkspace:
        """`interactive` is here for the caller that has no second stream to
        draw a prompt on - `--json` owns stdout."""
        return CleanWorkspace(
            executor=self.executor(dry_run=dry_run, verbose=verbose),
            file_system=self.file_system(dry_run=dry_run),
            prompt=self.prompt(
                # The confirmation is the only question `clean` asks, so
                # `--yes` leaves nothing to ask. A dry run removes nothing, so
                # there is nothing to consent to either.
                interactive=interactive and not (assume_yes or dry_run),
                assume_yes=assume_yes or dry_run,
            ),
            list_worktrees=list_worktrees,
        )
