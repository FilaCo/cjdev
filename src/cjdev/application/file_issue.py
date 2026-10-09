"""`cjdev issue new`: an upstream issue from the project's own issue form."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import final

from cjdev.application.build_units import HostProvider, build_environment
from cjdev.application.ports import Command, Executor, FileSystem, Forge, Prompt
from cjdev.domain.build import Profile
from cjdev.domain.environment import Environment
from cjdev.domain.forge import FiledIssue, NewIssue, parse_repository
from cjdev.domain.issue_form import IssueForm, read_draft, render_draft, version_field
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Manifest
from cjdev.errors import CjdevError, DraftError, PreconditionError

LoadForm = Callable[[Path], IssueForm]
TemplateNames = Callable[[Path], tuple[str, ...]]


@final
@dataclass(frozen=True)
class Outcome:
    issue: NewIssue
    filed: FiledIssue | None
    """None under `--dry-run`."""


@final
class FileIssue:
    def __init__(
        self,
        manifest: Callable[[], Manifest],
        executor: Executor,
        file_system: FileSystem,
        prompt: Prompt,
        forge: Forge,
        host: HostProvider,
        environment: Environment,
        load_form: LoadForm,
        template_names: TemplateNames,
        template_dir: PurePath,
    ) -> None:
        self._manifest = manifest
        self._executor = executor
        self._fs = file_system
        self._prompt = prompt
        self._forge = forge
        self._host = host
        self._environment = environment
        self._load_form = load_form
        self._template_names = template_names
        self._template_dir = template_dir

    def perform(
        self,
        root: Path,
        branch_set: str,
        project: str,
        template: str,
        *,
        profile: Profile,
        body: str | None = None,
    ) -> Outcome:
        """`body` is the filled draft; None opens the editor on one."""
        layout = WorkspaceLayout(root)
        repository = parse_repository(self._manifest().project(project).upstream_url)
        worktree = Path(layout.worktree(branch_set, project))
        form = self._form(worktree, template)

        draft = layout.issue_draft(branch_set, project, template)
        edited = body is None
        if body is None:
            body = self._edit(form, layout, branch_set, profile, worktree, draft)
        try:
            title, text = read_draft(form, body)
        except DraftError as exc:
            if not edited or not Path(draft).is_file():
                raise
            raise DraftError(
                str(exc), remedy=f"run it again to resume {draft}"
            ) from None

        issue = NewIssue(repository, title, text, form.labels)
        filed = self._forge.create_issue(issue)
        if filed is not None and Path(draft).is_file():
            self._fs.remove(draft)
        return Outcome(issue, filed)

    def _form(self, worktree: Path, template: str) -> IssueForm:
        if not worktree.is_dir():
            raise PreconditionError(
                f"{worktree.name} is not checked out in this branch set."
            )
        known = self._template_names(worktree)
        if template not in known:
            raise PreconditionError(
                f"{worktree.name} has no issue form {template!r}. "
                f"Known forms: {', '.join(known) or 'none'}."
            )
        return self._load_form(worktree / self._template_dir / f"{template}.yml")

    def _edit(
        self,
        form: IssueForm,
        layout: WorkspaceLayout,
        branch_set: str,
        profile: Profile,
        worktree: Path,
        draft: PurePath,
    ) -> str:
        if Path(draft).is_file():
            start = Path(draft).read_text(encoding="utf-8")
        else:
            field = version_field(form)
            version = (
                self._version(layout, branch_set, profile, worktree)
                if field is not None
                else None
            )
            prefill = {field.label: version} if field and version else {}
            start = render_draft(form, prefill)
        edited = self._prompt.edit(start, remedy="pass --body-file PATH")
        # Written before sending, so that neither a refused draft nor a forge
        # that is down costs the text.
        self._fs.mkdir(draft.parent)
        self._fs.write_text(draft, edited)
        return edited

    def _version(
        self, layout: WorkspaceLayout, branch_set: str, profile: Profile, cwd: Path
    ) -> str | None:
        """`cjc -v` of this branch set's dist, or None to leave the field for
        the person: a branch set not built yet still files issues."""
        where = self._environment.mode.value
        cjc = layout.sdk_path(branch_set, where, profile.value)[0] / "cjc"
        if not Path(cjc).is_file():
            return None
        try:
            done = self._executor.run(
                Command(
                    argv=(str(cjc), "-v"),
                    cwd=cwd,
                    env=build_environment(
                        layout, branch_set, where, profile, self._host()
                    ),
                    mutates=False,
                    what="reading cjc -v",
                ),
                check=False,
            )
        except CjdevError:
            return None
        output = (done.stdout or done.stderr).strip()
        return f"```text\n{output}\n```" if done.ok and output else None
