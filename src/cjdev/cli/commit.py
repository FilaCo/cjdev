import sys
from pathlib import Path

from typer import Exit, Option, Typer

from cjdev.application.commit_branch_set import Message
from cjdev.application.workspace import require_branch_set, require_root
from cjdev.errors import UsageError

from ._console import DETAIL, console
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin
from ._progress import Transcript
from ._render import commit_rows, render_rows

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def commit(
    ctx: CjdevContext,
    message: list[str] = Option(
        [], "--message", "-m", help="The message; repeated, one paragraph each."
    ),
    file: Path | None = Option(
        None, "--file", "-F", help="Read the message from a file, '-' for stdin."
    ),
    everything: bool = Option(
        False, "--all", "-a", help="Commit every tracked change, not only staged."
    ),
    signoff: bool = Option(
        True, "--signoff/--no-signoff", "-s", help="Add Signed-off-by."
    ),
    only: list[str] = Option(
        [], "--only", help="Commit in this project only; repeatable."
    ),
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Commit one change across the branch set you are standing in.

    One message in every project that has something to commit; the others
    are skipped. Signs off by default, like upstream's history.
    """
    begin("commit")
    text = _message(message, file)
    cwd = Path.cwd().resolve()
    root = require_root(cwd)
    branch_set = require_branch_set(root, cwd)

    transcript = Transcript()
    ctx.obj.emit = transcript.emit
    if not dry_run:
        ctx.obj.journal(root, ["commit", *(f"--only={p}" for p in only)])
    use_case = ctx.obj.commit_branch_set(dry_run=dry_run, verbose=verbose, start=root)

    plan = use_case.plan(
        root, branch_set, everything=everything, only=only, observer=transcript
    )
    report = use_case.apply(
        plan,
        Message(text=text, everything=everything, signoff=signoff),
        dry_run=dry_run,
        observer=transcript,
    )

    render_rows(
        console,
        commit_rows(report),
        interrupted=report.interrupted,
        lines=transcript.lines,
    )
    if dry_run:
        console.print("\nDry run: nothing was committed.", style=DETAIL)
    if not report.ok:
        raise Exit(1)


def _message(paragraphs: list[str], file: Path | None) -> str:
    """One text for every project, so a message read from stdin is read
    once rather than by the first project's commit alone."""
    if paragraphs and file is not None:
        raise UsageError("pass -m or -F, not both.")
    if file is None:
        if not paragraphs:
            raise UsageError("a commit message is required: -m or -F.")
        return "\n\n".join(paragraphs)
    if str(file) == "-":
        return sys.stdin.read()
    try:
        return file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise UsageError(f"cannot read the message from {file}: {exc}") from exc
