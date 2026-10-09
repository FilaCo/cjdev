"""`cjdev issue new`: from the project's form to the forge, with the editor,
the dist's `cjc` and the forge all faked."""

from pathlib import Path
from typing import final

import pytest

from cjdev.application.file_issue import FileIssue
from cjdev.application.ports import Command, Completed
from cjdev.domain.build import Host, Profile
from cjdev.domain.environment import Environment
from cjdev.domain.forge import FiledIssue, NewIssue
from cjdev.domain.issue_form import render_draft
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import Manifest, Project, ProjectRole
from cjdev.errors import DraftError, PreconditionError
from cjdev.infra.filesystem import HostFileSystem
from cjdev.infra.issue_template import TEMPLATE_DIR, load_form, template_names
from test_issue_form import BUG_FORM, VERSION, WHAT

SET = "fix"
PROJECT = "cangjie_compiler"
HOST = Host(
    target="linux_x86_64",
    jobs=1,
    path="/usr/bin",
    library_var="LD_LIBRARY_PATH",
    library_path="",
    ccache=None,
)
MANIFEST = Manifest(
    schema_version=1,
    projects=(
        Project(
            PROJECT,
            ProjectRole.BUILDABLE,
            "https://gitcode.com/Cangjie/cangjie_compiler.git",
            "main",
        ),
    ),
    build_units=(),
)


@final
class FakeExecutor:
    def __init__(self, stdout: str = "Cangjie Compiler: 1.0.0") -> None:
        self.ran: list[Command] = []
        self._stdout = stdout

    def run(self, command: Command, *, check: bool = True) -> Completed:
        self.ran.append(command)
        return Completed(command, 0, self._stdout, "")


@final
class Typist:
    """An editor that fills the draft in, and remembers what it was shown."""

    def __init__(self, *, title: str = "sema crashes", what: str = "It crashes."):
        self.shown: list[str] = []
        self._title = title
        self._what = what

    def confirm(self, question: str, *, destructive: bool = True) -> bool:
        raise AssertionError("nothing to confirm")

    def choose(self, question, options, *, preselected):
        raise AssertionError("nothing to choose")

    def select(self, question, options, *, default):
        raise AssertionError("nothing to select")

    def edit(self, draft: str, *, remedy: str) -> str:
        self.shown.append(draft)
        return (
            draft.replace("# [Bug]: ", f"# [Bug]: {self._title}", 1)
            .replace(f"### {WHAT}\n", f"### {WHAT}\n{self._what}\n", 1)
            .replace("- [ ] main", "- [x] main", 1)
        )


@final
class FakeForge:
    def __init__(self, *, dry: bool = False) -> None:
        self.filed: list[NewIssue] = []
        self._dry = dry

    def create_issue(self, issue: NewIssue) -> FiledIssue | None:
        self.filed.append(issue)
        return None if self._dry else FiledIssue("1", "https://gitcode.com/i/1")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    layout = WorkspaceLayout(tmp_path)
    forms = Path(layout.worktree(SET, PROJECT)) / TEMPLATE_DIR
    forms.mkdir(parents=True)
    (forms / "bug-report.yml").write_text(BUG_FORM, encoding="utf-8")
    return tmp_path


def built(root: Path) -> None:
    cjc = Path(WorkspaceLayout(root).sdk_path(SET, "host", "release")[0]) / "cjc"
    cjc.parent.mkdir(parents=True)
    cjc.write_text("")


def use_case(
    *,
    prompt: Typist | None = None,
    forge: FakeForge | None = None,
    executor: FakeExecutor | None = None,
) -> FileIssue:
    return FileIssue(
        manifest=lambda: MANIFEST,
        executor=executor or FakeExecutor(),
        file_system=HostFileSystem(),
        prompt=prompt or Typist(),
        forge=forge or FakeForge(),
        host=lambda: HOST,
        environment=Environment(),
        load_form=load_form,
        template_names=template_names,
        template_dir=TEMPLATE_DIR,
    )


def perform(case: FileIssue, root: Path, *, body: str | None = None):
    return case.perform(
        root, SET, PROJECT, "bug-report", profile=Profile.RELEASE, body=body
    )


def draft_of(root: Path) -> Path:
    return Path(WorkspaceLayout(root).issue_draft(SET, PROJECT, "bug-report"))


class TestFiling:
    def test_the_issue_goes_to_the_upstream_with_the_form_s_labels(self, root):
        # Arrange
        built(root)
        forge = FakeForge()

        # Act
        outcome = perform(use_case(forge=forge), root)

        # Assert
        issue = forge.filed[0]
        assert issue.repository.owner == "Cangjie"
        assert issue.repository.name == PROJECT
        assert issue.title == "[Bug]: sema crashes"
        assert issue.labels == ("bug",)
        assert outcome.filed is not None

    def test_the_version_comes_from_this_branch_set_s_dist(self, root):
        # Arrange
        built(root)
        executor, prompt = FakeExecutor(), Typist()

        # Act
        perform(use_case(executor=executor, prompt=prompt), root)

        # Assert
        command = executor.ran[0]
        assert command.argv[0].endswith(f"/dist/{SET}/host/release/bin/cjc")
        assert command.argv[1:] == ("-v",)
        assert not command.mutates
        assert "Cangjie Compiler: 1.0.0" in prompt.shown[0]

    def test_an_unbuilt_branch_set_leaves_the_version_to_the_person(self, root):
        # Arrange
        executor = FakeExecutor()

        # Act / Assert: the version is required, and nobody filled it in.
        with pytest.raises(DraftError, match="cjc version"):
            perform(use_case(executor=executor), root)
        assert executor.ran == []

    def test_a_body_file_is_sent_without_an_editor(self, root):
        # Arrange
        built(root)
        prompt, forge = Typist(), FakeForge()
        worktree = Path(WorkspaceLayout(root).worktree(SET, PROJECT))
        form = load_form(worktree / TEMPLATE_DIR / "bug-report.yml")
        body = Typist().edit(render_draft(form, {VERSION: "cjc 1.0"}), remedy="")

        # Act
        perform(use_case(prompt=prompt, forge=forge), root, body=body)

        # Assert
        assert prompt.shown == []
        assert forge.filed[0].title == "[Bug]: sema crashes"


class TestTheDraft:
    def test_a_refused_draft_is_kept_and_named(self, root):
        # Arrange
        built(root)
        case = use_case(prompt=Typist(what=""))

        # Act / Assert
        with pytest.raises(DraftError) as refusal:
            perform(case, root)
        assert refusal.value.remedy == f"run it again to resume {draft_of(root)}"
        assert draft_of(root).is_file()

    def test_the_next_run_resumes_it_instead_of_a_fresh_form(self, root):
        # Arrange
        built(root)
        with pytest.raises(DraftError):
            perform(use_case(prompt=Typist(what="")), root)
        prompt = Typist(what="It still crashes.")

        # Act
        perform(use_case(prompt=prompt), root)

        # Assert: the title typed the first time survived.
        assert prompt.shown[0].startswith("# [Bug]: sema crashes")

    def test_it_is_removed_once_the_forge_took_the_issue(self, root):
        # Arrange
        built(root)

        # Act
        perform(use_case(), root)

        # Assert
        assert not draft_of(root).exists()

    def test_a_dry_run_keeps_it(self, root):
        # Arrange
        built(root)

        # Act
        perform(use_case(forge=FakeForge(dry=True)), root)

        # Assert: nothing was filed, so the text is still wanted.
        assert draft_of(root).is_file()


class TestRefusals:
    def test_an_unknown_form_lists_the_known_ones(self, root):
        # Act / Assert
        with pytest.raises(PreconditionError, match="Known forms: bug-report"):
            use_case().perform(root, SET, PROJECT, "bug", profile=Profile.RELEASE)

    def test_a_project_not_in_the_branch_set_is_named(self, root):
        # Act / Assert
        with pytest.raises(PreconditionError, match="not checked out"):
            use_case().perform(
                root, "other", PROJECT, "bug-report", profile=Profile.RELEASE
            )
