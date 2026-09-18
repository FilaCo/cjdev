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

from cjdev.application.build_units import BuildUnits
from cjdev.application.init_workspace import InitWorkspace
from cjdev.application.new_branch_set import NewBranchSet
from cjdev.application.ports import Executor, FileSystem, Prompt
from cjdev.application.report_status import ReportStatus
from cjdev.application.workspace import find_root
from cjdev.domain.config import LayeredManifest, WorkspaceConfig, layer
from cjdev.domain.manifest import Manifest
from cjdev.infra.config import (
    load_bundled_manifest,
    load_workspace_config,
    render_workspace_config,
)
from cjdev.infra.executor import build_executor
from cjdev.infra.filesystem import build_file_system
from cjdev.infra.git import (
    add_checkout,
    drop_checkout,
    inspect_checkout,
    provision_object_store,
    read_store,
    remove_object_store,
)
from cjdev.infra.host import detect_host
from cjdev.infra.journal import CommandJournal, open_journal
from cjdev.infra.locks import file_lock, no_lock
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

    def manifest(self, start: Path | None = None) -> Manifest:
        """The effective project set: the bundled manifest with the nearest
        workspace's `.cjdev/config.toml` layered over it.

        `start` is where the caller stands; a walk up from there answers with
        the nearest workspace, so an inner one shadows an outer (FR-1). With
        no workspace in play - `config show` from a shell prompt, or tests -
        the bundled manifest alone applies (FR-9).

        Every command resolves its set through this one method, so a workspace
        override cannot take effect for `branch new` and not for `status`.
        """
        override = self._override(start)
        if override is None:
            return self._bundled
        return layer(self._bundled, override).effective

    def layered(self, start: Path | None = None) -> LayeredManifest:
        """The same answer as `manifest`, carrying the layer each value came
        from - for `config show` alone."""
        override = self._override(start)
        if override is None:
            # Outside a workspace the workspace layer is empty: the effective
            # config is the bundled manifest, and every layer says so.
            return layer(self._bundled, WorkspaceConfig())
        return layer(self._bundled, override)

    def _override(self, start: Path | None) -> WorkspaceConfig | None:
        if start is None:
            return None
        root = find_root(start)
        if root is None:
            return None
        # A workspace config that refuses to parse fails the command with the
        # message naming the file: acting on a set the user believes they
        # overrode is the worse outcome. The original error travels intact -
        # its code (`manifest`) and message already say everything this layer
        # would add.
        return load_workspace_config(root)

    @cached_property
    def _bundled(self) -> Manifest:
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
        and settings are different questions. Nothing supplies consent from the
        command line today; whatever eventually does must not also answer a
        wizard, or a script that only wanted to skip the questions would arm
        the deletions too.
        """
        if interactive and sys.stdin.isatty():
            return InteractivePrompt()
        return NonInteractivePrompt(assume_yes=assume_yes)

    def manifest_for_init(self, root: Path) -> Manifest:
        """The manifest `init` provisions from: the workspace it is creating
        or reconfiguring - never an enclosing one.

        `init` writes `.cjdev/` at `root`, so the override layer it may honour
        is `root`'s own file, and only when it already exists (a re-run that
        changes the project set). Walking up from `root`, the way `manifest`
        does, would answer a fresh nested `init` with the *enclosing*
        workspace's config - and the new workspace would be provisioned from
        an override its own file does not carry.
        """
        override = load_workspace_config(root)
        if override is None:
            return self._bundled
        return layer(self._bundled, override).effective

    def init_workspace(
        self, *, dry_run: bool = False, verbose: bool = False, start: Path
    ) -> InitWorkspace:
        return InitWorkspace(
            manifest=lambda: self.manifest_for_init(start),
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

    def new_branch_set(
        self, *, dry_run: bool = False, verbose: bool = False, start: Path
    ) -> NewBranchSet:
        """No `Prompt`: the whole input is the name, and nothing of the
        user's is at stake, so there is no question to ask and nothing to
        refuse for the lack of a terminal."""
        return NewBranchSet(
            manifest=lambda: self.manifest(start),
            executor=self.executor(dry_run=dry_run, verbose=verbose),
            file_system=self.file_system(dry_run=dry_run),
            inspect=inspect_checkout,
            add=add_checkout,
            drop=drop_checkout,
        )

    def build_units(
        self, *, dry_run: bool = False, verbose: bool = False, start: Path
    ) -> BuildUnits:
        """No `Prompt`: a build creates and overwrites only what cjdev owns,
        so there is nothing to ask consent for."""
        return BuildUnits(
            manifest=lambda: self.manifest(start),
            executor=self.executor(dry_run=dry_run, verbose=verbose),
            file_system=self.file_system(dry_run=dry_run),
            host=detect_host(),
            # A dry run leaves no lock file behind: it starts no build, so
            # there is nothing for a second one to collide with.
            lock=no_lock if dry_run else file_lock,
        )

    def report_status(
        self, *, verbose: bool = False, manifest: Manifest
    ) -> ReportStatus:
        """No `FileSystem` and no `Prompt`: it changes nothing, so there is
        nothing to make dry, and nothing to ask permission for.

        The manifest arrives already resolved: the CLI needs it before the
        fan-out (the transcript flush has labels to fall back on), and the
        same instance travelling down is what keeps one command to one read
        of the workspace config."""
        return ReportStatus(
            manifest=lambda: manifest,
            executor=self.executor(verbose=verbose),
            read_store=read_store,
        )
