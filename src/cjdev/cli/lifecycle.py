from contextlib import ExitStack
from pathlib import Path

from typer import Typer, prompt

from cjdev.application.workspace import require_branch_set, require_root
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import PreconditionError
from cjdev.infra.locks import file_lock
from cjdev.infra.record import read_record
from cjdev.infra.task_checkout import inspect, publish, retire

from ._context import CjdevCommand, CjdevContext, CjdevGroup
from ._output import begin
from .start import new_issue

cli = Typer(cls=CjdevGroup)


@cli.command(cls=CjdevCommand)
def ship(ctx: CjdevContext) -> None:
    """Publish committed changes and link each PR to the task issue."""
    begin("ship")
    cwd = Path.cwd().resolve()
    root = require_root(cwd)
    name = require_branch_set(root, cwd)
    layout = WorkspaceLayout(root)
    executor = ctx.obj.executor()
    changed = [
        c for c in inspect(executor, layout, name, ctx.obj.manifest(root)) if c.ahead
    ]
    if not changed:
        print("No projects ahead of upstream.")
        return
    task = read_record(layout.record(name)).task
    issue = task.issue if task else None
    if not issue:
        tasks = ctx.obj.tasks(start=root)
        choice = ctx.obj.prompt().select(
            "Task issue", ["Existing issue", "New issue"], default="Existing issue"
        )
        if choice == "New issue":
            linked = new_issue(ctx, root, name, task.home if task else None, False).task
        else:
            linked = tasks.start(
                prompt("Issue (project#number or URL)"),
                no_issue=False,
                name=name,
                home=None,
            ).task
        tasks.remember(root, name, linked)
        issue = linked.issue
    if not issue:
        raise PreconditionError("publishing requires a task issue")
    for checkout in changed:
        print(publish(executor, ctx.obj.gitcode(), checkout, issue))


@cli.command(cls=CjdevCommand)
def done(ctx: CjdevContext) -> None:
    """Remove this finished task's local branches, checkouts and artifacts."""
    begin("done")
    cwd = Path.cwd().resolve()
    root = require_root(cwd)
    name = require_branch_set(root, cwd)
    layout = WorkspaceLayout(root)
    if not read_record(layout.record(name)).task:
        raise PreconditionError(f"{name} has no recorded task")
    executor = ctx.obj.executor()
    if not ctx.obj.prompt().confirm(
        f"Remove local branch set {name} and its build, dist, drafts and logs?"
    ):
        return
    artifacts = [
        Path(layout.marker / category / name)
        for category in ("build", "dist", "log", "drafts")
    ]
    for path in [*artifacts, Path(layout.record(name))]:
        if path.resolve() != path:
            raise PreconditionError(f"{path.parent} redirects outside the task layout")
    with ExitStack() as locks:
        for unit in ctx.obj.manifest(root).build_units:
            locks.enter_context(file_lock(layout.build_lock(name, unit.name)))
        checkouts = inspect(executor, layout, name, ctx.obj.manifest(root))
        retire(executor, ctx.obj.gitcode(), checkouts, layout, name)
        fs = ctx.obj.file_system()
        for path in artifacts:
            if path.exists() or path.is_symlink():
                fs.remove(path)
        fs.remove(layout.record(name))
    print(f"Removed {name}. Workspace: {root}")
