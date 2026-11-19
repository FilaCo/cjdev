from pathlib import Path

from rich.table import Column, Table
from rich.text import Text
from typer import Option, Typer

from cjdev.application.manage_dependencies import DependencyRequest, DependencyRow
from cjdev.application.workspace import require_branch_set, require_root

from ._console import console
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin

cli = Typer(
    cls=CjdevGroup,
    name="deps",
    help="Select third-party sources for the current branch set.",
)


def _current() -> tuple[Path, str]:
    cwd = Path.cwd().resolve()
    root = require_root(cwd)
    return root, require_branch_set(root, cwd)


def _show(rows: list[DependencyRow]) -> None:
    table = Table(
        "Unit",
        "Dependency",
        Column("Upstream", overflow="fold"),
        Column("Ref", overflow="fold"),
        "Linked",
        Column("Set by", overflow="fold"),
        padding=(0, 0),
    )
    for row in rows:
        table.add_row(
            Text(row.unit),
            Text(row.source.name),
            Text(row.source.upstream),
            Text(row.source.ref),
            Text(row.linked[:8] if row.linked else "—"),
            Text(row.origin),
        )
    console.print(table)


@cli.callback(invoke_without_command=True)
def deps(ctx: CjdevContext) -> None:
    """Show requested sources and linked commits, without contacting upstream."""
    if ctx.invoked_subcommand is None:
        begin("deps")
        _show(ctx.obj.manage_dependencies(*_current()).run())


def _change(ctx: CjdevContext, request: DependencyRequest, dry_run: bool) -> None:
    root, branch = _current()
    if not dry_run:
        args = [
            "deps",
            "set" if request.ref is not None else "reset",
            request.unit,
            request.name,
        ]
        if request.ref is not None:
            args.append(request.ref)
        if request.upstream is not None:
            args.extend(["--upstream", request.upstream])
        ctx.obj.journal(root, args)
    use_case = ctx.obj.manage_dependencies(root, branch, dry_run=dry_run)
    _show(use_case.run(request))


@cli.command("set", cls=CjdevCommand)
def select(
    ctx: CjdevContext,
    unit: str,
    dependency: str,
    ref: str,
    dry_run: bool = Option(False, "--dry-run", help="Preview the selection."),
    upstream: str | None = Option(
        None, "--upstream", help="Git URL. Omit to keep the current source."
    ),
) -> None:
    """Select a branch, tag or full commit SHA for subsequent builds."""
    begin("deps set")
    _change(ctx, DependencyRequest(unit, dependency, ref, upstream), dry_run)


@cli.command(cls=CjdevCommand)
def reset(
    ctx: CjdevContext,
    unit: str,
    dependency: str,
    dry_run: bool = Option(False, "--dry-run", help="Preview the inherited selection."),
) -> None:
    """Restore the inherited upstream and ref for subsequent builds."""
    begin("deps reset")
    _change(ctx, DependencyRequest(unit, dependency, None), dry_run)
