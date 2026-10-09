from pathlib import Path

from typer import Argument, Exit, Option, Typer

from cjdev.application.workspace import require_branch_set, require_root
from cjdev.domain.build import Profile

from ._console import DETAIL, console
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin
from ._render import render_tests
from .build import split_passthrough

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand, context_settings={"ignore_unknown_options": True})
def test(
    ctx: CjdevContext,
    paths: list[str] = Argument(
        None,
        help=(
            "Test cases or directories under cangjie_test/testsuites/LLT or "
            "HLT. After `--`, a flag and everything following it are passed "
            "to the framework's main.py."
        ),
    ),
    profile: Profile | None = Option(
        None,
        "-p",
        "--profile",
        help="Whose SDK to test. Default: the branch set's, from its last full build.",
    ),
    dry_run: bool = Option(False, "--dry-run", help="Print the commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Run the test framework against the branch set you are standing in.

    Inside the build environment, against the branch set's own dist, with the
    test list and config of each path's suite for this host and `-pFAIL
    --fail-verbose`. Scratch, logs and results go under
    `.cjdev/build/<set>/test/`, and the summary counts the failures that are
    a missing tool apart from the rest.
    """
    begin("test")
    cwd = Path.cwd().resolve()
    root = require_root(cwd)
    # The dist under test is the one of the worktrees the caller stands in.
    branch_set = require_branch_set(root, cwd)
    named, passthrough = split_passthrough(paths or [])
    if not dry_run:
        ctx.obj.journal(root, ["test", *(paths or [])])

    chosen = ctx.obj.branch_set_profile(dry_run=dry_run, start=root).resolve(
        root, branch_set, profile
    )
    use_case = ctx.obj.run_tests(dry_run=dry_run, verbose=verbose, start=root)
    plan = use_case.plan(
        root,
        branch_set,
        profile=chosen,
        paths=[cwd / name for name in named],
        cwd=cwd,
        passthrough=passthrough,
    )
    report = use_case.apply(plan)

    if dry_run:
        console.print("\nDry run: nothing ran.", style=DETAIL)
        return
    render_tests(console, report)
    if not report.ok:
        raise Exit(1)
