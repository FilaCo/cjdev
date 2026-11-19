from pathlib import Path

from rich.table import Column, Table
from rich.text import Text
from typer import Option, Typer

from cjdev.application.third_party import observe
from cjdev.application.workspace import require_branch_set, require_root
from cjdev.domain.dependencies import effective
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import PreconditionError
from cjdev.infra.record import change_dependency, read_record

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


def _show(
    ctx: CjdevContext, root: Path, branch: str, only: tuple[str, str] | None = None
) -> None:
    layout = WorkspaceLayout(root)
    choices = read_record(layout.record(branch)).dependencies
    layered = ctx.obj.layered(root)
    table = Table(
        "Unit",
        "Dependency",
        Column("Upstream", overflow="fold"),
        Column("Ref", overflow="fold"),
        "Linked",
        Column("Set by", overflow="fold"),
        padding=(0, 0),
    )
    for unit, layers in zip(
        layered.effective.build_units, layered.build_units, strict=True
    ):
        for source, seen in zip(
            unit.third_party, observe(layout, branch, unit), strict=True
        ):
            key = (unit.name, source.name)
            if only and key != only:
                continue
            selected = effective(unit.name, source, choices)
            origin = branch if key in choices else layers.third_party.layer
            table.add_row(
                Text(unit.name),
                Text(source.name),
                Text(selected.upstream),
                Text(selected.ref),
                Text(seen.commit[:8] if seen.commit else "—"),
                Text(origin),
            )
    console.print(table)


@cli.callback(invoke_without_command=True)
def deps(ctx: CjdevContext) -> None:
    """Show requested sources and linked commits, without contacting upstream."""
    if ctx.invoked_subcommand is None:
        begin("deps")
        _show(ctx, *_current())


def _change(
    ctx: CjdevContext, unit: str, dependency: str, ref: str | None, upstream: str | None
) -> None:
    root, branch = _current()
    sources = ctx.obj.manifest(root).unit(unit).third_party
    matches = [source for source in sources if source.name == dependency]
    if not matches:
        known = ", ".join(source.name for source in sources) or "none"
        raise PreconditionError(
            f"Unknown dependency {dependency} for {unit}. Known dependencies: {known}."
        )
    if len(matches) > 1:
        raise PreconditionError(
            f"Multiple dependencies in {unit} are named {dependency}."
        )
    if any(value is not None and not value.strip() for value in (ref, upstream)):
        raise PreconditionError("A dependency ref and upstream must be non-empty.")
    change_dependency(
        WorkspaceLayout(root).record(branch), unit, dependency, ref, upstream
    )
    _show(ctx, root, branch, (unit, dependency))


@cli.command("set", cls=CjdevCommand)
def select(
    ctx: CjdevContext,
    unit: str,
    dependency: str,
    ref: str,
    upstream: str | None = Option(
        None, "--upstream", help="Git URL. Omit to keep the current source."
    ),
) -> None:
    """Select a branch, tag or full commit SHA for subsequent builds."""
    begin("deps set")
    _change(ctx, unit, dependency, ref, upstream)


@cli.command(cls=CjdevCommand)
def reset(ctx: CjdevContext, unit: str, dependency: str) -> None:
    """Restore the inherited upstream and ref for subsequent builds."""
    begin("deps reset")
    _change(ctx, unit, dependency, None, None)
