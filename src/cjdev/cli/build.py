from typer import Argument, Typer

from cjdev.errors import NotImplementedYetError
from cjdev.infra.config import load_bundled_manifest

from ._context import CjdevCommand, CjdevContext, CjdevGroup

cli = Typer(cls=CjdevGroup)


def complete_unit(incomplete: str) -> list[str]:
    """Unit names for the shell.

    Completion runs in its own process with no context, so this reads the
    shipped manifest rather than the effective one. A workspace that overrides
    the unit set will complete the defaults
    """
    return [
        unit.name
        for unit in load_bundled_manifest().build_units
        if unit.name.startswith(incomplete)
    ]


@cli.command(cls=CjdevCommand)
def build(
    ctx: CjdevContext,
    units: list[str] = Argument(
        None,
        help="Build units to build. Defaults to the whole SDK.",
        autocompletion=complete_unit,
    ),
) -> None:
    """Build Cangjie SDK build units, in dependency order."""
    ordered = ctx.obj.manifest.build_order(units or None)

    raise NotImplementedYetError(
        f"building {', '.join(unit.name for unit in ordered)}", "M2"
    )
