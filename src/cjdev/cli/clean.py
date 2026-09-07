from pathlib import Path

from typer import Argument, Option, Typer

from cjdev.application.workspace import find_root, require_root
from cjdev.errors import PreconditionError

from ._console import DETAIL, console
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._render import render_clean_plan

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def clean(
    ctx: CjdevContext,
    path: Path | None = Argument(None, help="The workspace. Defaults to the cwd."),
    force: bool = Option(
        False, "-f", "--force", help="Delete even while worktrees still use it."
    ),
    dry_run: bool = Option(
        False, "--dry-run", help="Print what would go, remove none."
    ),
    verbose: bool = Option(False, "-v", "--verbose", help="Echo every command."),
    assume_yes: bool = Option(False, "-y", "--yes", help="Skip the confirmation."),
) -> None:
    """Empty this workspace: worktrees, object stores and all."""
    root = _root(path)
    # Straight to the terminal: `clean` has no fan-out, so there is no
    # scheduling for the order of these lines to depend on, and holding them
    # back until the end would mean printing a dry run's plan after it.
    ctx.obj.emit = lambda line: console.print(
        line, style=DETAIL, highlight=False, soft_wrap=True
    )
    if not dry_run:
        # The log lives inside what is about to be deleted, which is right:
        # the record of a workspace goes when the workspace does. The handle
        # stays open across the removal and simply stops mattering.
        ctx.obj.journal(root, ["clean", str(root)])

    plan = ctx.obj.clean_workspace(
        dry_run=dry_run, verbose=verbose, assume_yes=assume_yes
    ).perform(root, force=force)

    render_clean_plan(console, plan, dry_run=dry_run)


def _root(path: Path | None) -> Path:
    """A named path must *be* a workspace; only the cwd is searched upwards.

    Walking up from an argument would let `cjdev clean ./notes` empty the
    parent directory that happens to be a workspace, which is not what anyone
    typing that meant.
    """
    if path is None:
        return require_root(Path.cwd())
    resolved = path.resolve()
    if find_root(resolved) != resolved:
        raise PreconditionError(f"{resolved} is not a cjdev workspace root.")
    return resolved
