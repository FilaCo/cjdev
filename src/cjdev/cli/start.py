from pathlib import Path

from typer import Argument, Option, Typer, prompt

from cjdev.application.task import Start
from cjdev.application.workspace import held_projects, require_root
from cjdev.domain.build import Profile
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.record import Task, task_name
from cjdev.errors import PreconditionError
from cjdev.infra.config import load_issue_home
from cjdev.infra.issue_template import UpstreamForms

from ._console import diagnostics
from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin
from .branch import check_out, finish, progress_for

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def start(
    ctx: CjdevContext,
    subject: str | None = Argument(
        None, help="Issue URL or project#number. Omit to choose a workflow."
    ),
    name: str | None = Option(
        None, "--name", help="The branch set, instead of issue-<n>-<title>."
    ),
    no_issue: bool = Option(
        False, "--no-issue", help="Start without an issue; attach one later."
    ),
    home: str | None = Option(
        None,
        "--home",
        help="With --no-issue: the project the issue will live in. "
        "Defaults to forge.issue_home in .cjdev/config.toml.",
    ),
    dry_run: bool = Option(False, "--dry-run", help="Print commands, run none."),
    verbose: bool = Option(False, "-v", "--verbose", help="Show more detail."),
) -> None:
    """Start a task: a branch set for an issue, cut from fresh upstream.

    Reads the issue from GitCode (token: GITCODE_TOKEN, else git's stored
    credential for gitcode.com), names the branch set issue-<n>-<title>,
    fetches upstream in every project and branches from its default branch.
    The issue is remembered for later commands. Run it inside the workspace.
    """
    out = begin("start")
    root = require_root(Path.cwd().resolve())
    progress = progress_for(out, dry_run=dry_run)
    ctx.obj.emit = progress.emit
    ctx.obj.report_step = progress.step
    if not dry_run:
        ctx.obj.journal(
            root,
            [
                "start",
                subject or "",
                *(["--no-issue"] if no_issue else []),
                *([f"--name={name}"] if name else []),
                *([f"--home={home}"] if home else []),
            ],
        )
    tasks = ctx.obj.tasks(dry_run=dry_run, verbose=verbose, start=root)

    if subject is None:
        mode = (
            "Experiment"
            if no_issue
            else ctx.obj.prompt().select(
                "Start work",
                ["New issue", "Existing issue", "Experiment"],
                default="New issue",
            )
        )
        if mode == "New issue":
            started = new_issue(ctx, root, "new-task", home, dry_run)
        elif mode == "Existing issue":
            started = tasks.start(
                prompt("Issue (project#number or URL)"),
                no_issue=False,
                name=name,
                home=None,
            )
        else:
            started = tasks.start(
                name or prompt("Branch set"), no_issue=True, name=None, home=home
            )
        if mode != "Experiment":
            started = Start(
                name or prompt("Branch set", default=started.branch_set), started.task
            )
    else:
        started = tasks.start(subject, no_issue=no_issue, name=name, home=home)
    if (
        subject is None
        and Path(WorkspaceLayout(root).branch_set_dir(started.branch_set)).exists()
    ):
        raise PreconditionError(f"branch set {started.branch_set} already exists")
    if not dry_run:
        diagnostics.print("Fetching upstream...", highlight=False)
    tasks.fetch(root, observer=progress.transcript)
    report = check_out(
        ctx, root, started.branch_set, progress, dry_run=dry_run, verbose=verbose
    )
    if report.ok:
        tasks.remember(root, started.branch_set, started.task)
    finish(out, root, report, progress, as_json=False, dry_run=dry_run)


def new_issue(
    ctx: CjdevContext, root: Path, branch: str, home: str | None, dry_run: bool
) -> Start:
    layout = WorkspaceLayout(root)
    manifest = ctx.obj.manifest(root)
    projects = [
        name
        for name in held_projects(layout, manifest)
        if name in {p.name for p in manifest.projects}
    ]
    if not projects:
        raise PreconditionError("the workspace holds no projects")
    default = home or load_issue_home(root)
    project = ctx.obj.prompt().select(
        "Issue project",
        projects,
        default=default if default in projects else projects[0],
    )
    store = Path(layout.object_store(project))
    upstream = UpstreamForms(ctx.obj.executor(), store)
    forms = upstream.names()
    if not forms:
        raise PreconditionError(f"{project} has no issue forms")
    template = ctx.obj.prompt().select("Issue template", forms, default=forms[0])
    form = upstream.load(template)
    outcome = ctx.obj.file_issue(start=root, dry_run=dry_run).perform(
        root, branch, project, template, profile=Profile.RELEASE, form=form
    )
    filed = outcome.filed
    if filed:
        print(filed.url)
    return Start(
        task_name(filed.number if filed else "N", outcome.issue.title),
        Task(project, filed.url if filed else None),
    )
