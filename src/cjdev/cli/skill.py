from pathlib import Path

from typer import Option, Typer

from cjdev.application.install_skill import Outcome

from ._console import DETAIL, OK, console
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin

cli = Typer(
    cls=CjdevGroup,
    name="skill",
    help="The agent skill for driving cjdev, shipped with this version.",
    no_args_is_help=True,
)

USER_SKILLS = Path("~/.claude/skills")


@cli.command(cls=CjdevCommand)
def show(ctx: CjdevContext) -> None:
    """Print the skill, for an agent cjdev does not install into."""
    begin("skill show")
    # `print`, not the console: Markdown is full of brackets rich would take
    # for markup, and the text is meant to be piped into a file.
    print(ctx.obj.skill(), end="")


@cli.command(cls=CjdevCommand)
def install(
    ctx: CjdevContext,
    skills_dir: Path = Option(
        USER_SKILLS,
        "--dir",
        help="The skills directory to install into, e.g. ~/.agents/skills for Codex.",
    ),
    dry_run: bool = Option(False, "--dry-run", help="Print the write, do none."),
) -> None:
    """Install the skill as cjdev/SKILL.md in a skills directory.

    User-level by default rather than in the workspace: Claude Code looks for
    project skills only up to the git repository root, and every project of a
    branch set is a repository of its own.
    """
    begin("skill install")
    target, outcome = ctx.obj.install_skill(dry_run=dry_run).perform(
        skills_dir.expanduser().resolve()
    )
    if outcome is Outcome.CURRENT:
        console.print(f"{target} is up to date.", style=DETAIL, soft_wrap=True)
    elif dry_run:
        console.print("\nDry run: nothing was written.", style=DETAIL)
    else:
        console.print(f"Skill {outcome.value}: {target}", style=OK, soft_wrap=True)
