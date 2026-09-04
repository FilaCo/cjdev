from pathlib import Path

from typer import Argument, Option, Typer

from cjdev.application.workspace import find_root, require_root
from cjdev.errors import PreconditionError

from ._console import console
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
