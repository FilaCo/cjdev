from collections.abc import Sequence
from pathlib import Path

from typer import Argument, Exit, Option, Typer

from cjdev.application.workspace import require_branch_set, require_root
from cjdev.domain.build import Profile

from ._console import DETAIL, OK, console, diagnostics
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin, from_error
from ._progress import LIVE_AFTER, ConsoleProgress
from ._render import build_payload, render_build

cli = Typer(cls=CjdevGroup)


def split_passthrough(tokens: Sequence[str]) -> tuple[list[str], list[str]]:
    """Unit names, then everything meant for the build script.

    Click drops the `--` before the arguments reach the command, so the split
    is made on the first token that looks like a flag. `--` is still the way to
    write it, and still what the help says, because anything else would be
    parsed as one of cjdev's own options.
    """
    for index, token in enumerate(tokens):
        if token.startswith("-"):
            return list(tokens[:index]), list(tokens[index:])
    return list(tokens), []


@cli.command(cls=CjdevCommand, context_settings={"ignore_unknown_options": True})
def build(
    ctx: CjdevContext,
    units: list[str] = Argument(
        None,
        help=(
            "Build units or projects to build, with their dependencies. "
            "Default: the whole SDK. Anything after `--` is passed to the "
            "build script, and then exactly one unit may be named."
        ),
    ),
    profile: Profile = Option(
        Profile.RELEASE.value,
        "-p",
        "--profile",
        help="Which build to make. Each profile keeps its own build directory.",
    ),
    downstream: str | None = Option(
        None,
        "--from",
        help="Build this unit and everything that depends on it.",
    ),
    as_json: bool = Option(False, "--json", help="Print the report as JSON."),
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Build the SDK from the branch set you are standing in.

    One unit at a time, in dependency order, out of tree: each unit's scratch
    directories are symlinked into `.cjdev/build/<set>/<profile>/`, so
    switching profiles costs nothing and two branch sets never share a build.

    There is no --workspace: the cwd names the branch set as well as the
    workspace, and a flag that answered only half of that would be worse than
    the cd it saves.
    """
    out = begin("build", as_json=as_json)
    cwd = Path.cwd().resolve()
    root = require_root(cwd)
    # Which branch set is not a flag: the worktrees a build compiles are the
    # ones the caller is standing in.
    branch_set = require_branch_set(root, cwd)
    names, passthrough = split_passthrough(units or [])

    progress = ConsoleProgress(
        out.display,
        fallback=None if dry_run else diagnostics,
        delay=LIVE_AFTER,
        transient=True,
    )
    ctx.obj.emit = progress.emit
    ctx.obj.report_step = progress.step
    if not dry_run:
        ctx.obj.journal(root, ["build", *(units or [])])
    use_case = ctx.obj.build_units(dry_run=dry_run, verbose=verbose, start=root)

    plan = use_case.plan(
        root,
        branch_set,
        profile=profile,
        names=names,
        downstream=downstream,
        passthrough=passthrough,
    )
    progress.track(
        [unit.unit for unit in plan.units],
        title=f"Building {branch_set} ({profile.value})",
        # One job always: each script already takes the whole machine, so the
        # estimate must not divide by anything.
        jobs=1,
    )

    with progress:
        report = use_case.apply(plan, observer=progress)

    if as_json:
        out.document(
            build_payload(report),
            ok=report.ok,
            errors=[
                from_error(row.error, subject=row.unit)
                for row in report.failures
                if row.error is not None
            ],
        )
    else:
        render_build(console, report, lines=progress.lines)
        if dry_run:
            console.print(
                f"\nDry run: {root} was not touched.", style=DETAIL, soft_wrap=True
            )
        elif report.ok:
            console.print(
                f"\nCANGJIE_HOME={plan.dist}", style=OK, soft_wrap=True, highlight=False
            )
        else:
            console.print(f"\n{progress.summary()}", style=DETAIL, highlight=False)

    if not dry_run and not report.ok:
        raise Exit(1)
