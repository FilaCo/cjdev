from pathlib import Path

from typer import Argument, Option, Typer

from cjdev.application.workspace import require_branch_set, require_root
from cjdev.domain.build import Profile

from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin

cli = Typer(
    cls=CjdevGroup,
    name="issue",
    help="Upstream issues, from each project's own issue forms.",
)


@cli.command(cls=CjdevCommand)
def new(
    ctx: CjdevContext,
    project: str = Argument(..., help="The project whose upstream gets the issue."),
    template: str = Option(
        ...,
        "--template",
        "-t",
        help="The form: a file in .gitcode/ISSUE_TEMPLATE/, without .yml.",
    ),
    body_file: Path | None = Option(
        None,
        "--body-file",
        help="A filled draft to send, instead of opening $EDITOR.",
        exists=True,
        dir_okay=False,
    ),
    profile: Profile = Option(
        Profile.RELEASE.value,
        "-p",
        "--profile",
        help="Which build's cjc answers `cjc -v` in the draft.",
    ),
    dry_run: bool = Option(False, "--dry-run", help="Print the request, send nothing."),
) -> None:
    """File an issue on PROJECT's upstream from one of its issue forms.

    The form becomes a Markdown draft in $EDITOR, one `###` section per field,
    with `cjc -v` of this branch set's dist filled in. A required field left
    empty is refused before anything is sent, and the draft is kept for the
    next run. The token is GITCODE_TOKEN, else git's stored credential for
    gitcode.com. Run it from inside a branch set: the form is that checkout's.
    """
    begin("issue new")
    cwd = Path.cwd().resolve()
    root = require_root(cwd)
    branch_set = require_branch_set(root, cwd)
    if not dry_run:
        ctx.obj.journal(root, ["issue", "new", project, "--template", template])
    body = body_file.read_text(encoding="utf-8") if body_file else None

    outcome = ctx.obj.file_issue(dry_run=dry_run, start=root).perform(
        root, branch_set, project, template, profile=profile, body=body
    )

    # print, not rich: a title like `[Bug]: ...` is markup to rich.
    if outcome.filed is not None:
        print(outcome.filed.url)
