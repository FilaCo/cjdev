from pathlib import Path

from typer import Argument, Exit, Option, Typer

from cjdev.application.workspace import require_branch_set, require_root
from cjdev.domain.build import Profile

from ._console import DETAIL, OK, console
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin

cli = Typer(
    cls=CjdevGroup,
    name="env",
    help="The environment builds run in.",
)

PROFILE = Option(
    Profile.RELEASE.value,
    "-p",
    "--profile",
    help="Whose build environment to use. Each profile has its own SDK.",
)


@cli.command(cls=CjdevCommand)
def build(
    ctx: CjdevContext,
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Build the image this workspace's builds run in.

    The tag carries the hash of the Dockerfile that ships with cjdev, so
    upgrading cjdev and getting a new recipe is a new tag - and `cjdev build`
    asks for this command by name rather than quietly building minutes of
    image in the middle of something else.
    """
    begin("env build")
    root = require_root(Path.cwd().resolve())
    if not dry_run:
        ctx.obj.journal(root, ["env", "build"])

    ctx.obj.manage_environment(dry_run=dry_run, verbose=verbose, start=root).build(root)

    if dry_run:
        console.print(f"\nDry run: {root} was not touched.", style=DETAIL)
    else:
        console.print("Image ready.", style=OK)


@cli.command(cls=CjdevCommand, name="rm")
def remove(
    ctx: CjdevContext,
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Remove the image, which is the only state container mode leaves behind.

    There is no container to stop: every command runs its own and takes it with
    it.

    Only the image this cjdev's Dockerfile hashes to. An upgrade that changed
    the recipe left the tag before it on the machine, and removing that one is
    `docker image rm cjdev-build:<hash>` for now.
    """
    begin("env rm")
    root = require_root(Path.cwd().resolve())
    if not dry_run:
        ctx.obj.journal(root, ["env", "rm"])

    ctx.obj.manage_environment(dry_run=dry_run, verbose=verbose, start=root).remove()

    if dry_run:
        console.print(f"\nDry run: {root} was not touched.", style=DETAIL)


@cli.command(cls=CjdevCommand, context_settings={"ignore_unknown_options": True})
def run(
    ctx: CjdevContext,
    argv: list[str] = Argument(
        None,
        help="The command to run. Put `--` before it, or its flags become cjdev's.",
    ),
    profile: Profile = PROFILE,
    dry_run: bool = Option(False, "--dry-run", help="Print the command, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Run one command with the build environment of the branch set you are in.

    The same mount, the same working directory, the same variables and the same
    image a `cjdev build` step gets, so the argv the workspace log recorded is
    one you can run again by hand. In host mode it runs here, with the same
    environment.
    """
    _inside(ctx, "env run", profile, tuple(argv or ()), dry_run, verbose)


@cli.command(cls=CjdevCommand)
def shell(
    ctx: CjdevContext,
    profile: Profile = PROFILE,
    dry_run: bool = Option(False, "--dry-run", help="Print the command, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """A shell in the build environment. `env run` with nothing to run."""
    _inside(ctx, "env shell", profile, (), dry_run, verbose)


def _inside(
    ctx: CjdevContext,
    what: str,
    profile: Profile,
    argv: tuple[str, ...],
    dry_run: bool,
    verbose: bool,
) -> None:
    begin(what)
    cwd = Path.cwd().resolve()
    root = require_root(cwd)
    # Which branch set is not a flag, for `build`'s reason: the environment is
    # the one of the worktrees the caller is standing in.
    branch_set = require_branch_set(root, cwd)
    if not dry_run:
        ctx.obj.journal(root, [*what.split(), *argv])

    code = ctx.obj.manage_environment(dry_run=dry_run, verbose=verbose, start=root).run(
        root, branch_set, profile=profile, cwd=cwd, argv=argv
    )

    if dry_run:
        console.print("\nDry run: nothing ran.", style=DETAIL)
    elif code:
        # The command's own exit code, not a cjdev failure: `env run` did its
        # job by running what it was given.
        raise Exit(code)
