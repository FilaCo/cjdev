"""Issue forms: reading the upstream YAML, rendering the draft, and the
required-field check the forge itself never makes."""

from pathlib import Path

import pytest

from cjdev.domain.issue_form import (
    NO_RESPONSE,
    FieldKind,
    read_draft,
    render_draft,
    version_field,
)
from cjdev.errors import DraftError, PreconditionError
from cjdev.infra.issue_template import TEMPLATE_DIR, load_form, template_names

# Trimmed from cangjie_compiler's own bug-report.yml, entities and all.
BUG_FORM = """\
name: "缺陷反馈|Bug"
description: "当您发现了一个缺陷 &#124; Please use this template when you find a bug."
title: "[Bug]: "
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        感谢对仓颉社区的支持与关注 | Thanks for your support.
  - type: textarea
    attributes:
      label: "发生了什么问题？ | Describe the issue that occurred."
      description: "提供尽可能多的信息 &#124; Provide as much information as possible."
      placeholder: ""
    validations:
      required: true
  - type: textarea
    attributes:
      label: "其他补充信息 | Additional information"
      description: "补充下其他您认为需要提供的信息"
    validations:
      required: false
  - type: textarea
    attributes:
      label: "cjc版本信息 | cjc version information "
      description: "请将cjc -v的输出结果填写在下方"
    validations:
      required: true
  - type: dropdown
    id: domain
    attributes:
      label: "领域 | Domain"
      options:
        - Tools
        - LSP
    validations:
      required: false
  - type: checkboxes
    attributes:
      label: "分支版本信息 | Branch version information"
      options:
        - label: dev
          required: false
        - label: main
          required: false
    validations:
      required: true
"""  # noqa: RUF001 - upstream's own fullwidth question mark

WHAT = "发生了什么问题？ | Describe the issue that occurred."  # noqa: RUF001
EXTRA = "其他补充信息 | Additional information"
VERSION = "cjc版本信息 | cjc version information"
BRANCHES = "分支版本信息 | Branch version information"


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    directory = tmp_path / TEMPLATE_DIR
    directory.mkdir(parents=True)
    (directory / "bug-report.yml").write_text(BUG_FORM, encoding="utf-8")
    (directory / "config.yml").write_text("blank_issues_enabled: false\n")
    return tmp_path


def filled(draft: str, **replace: str) -> str:
    for old, new in replace.items():
        draft = draft.replace(old, new, 1)
    return draft


class TestLoadingAForm:
    def test_the_greeting_is_not_a_field(self, worktree: Path):
        # Act
        form = load_form(worktree / TEMPLATE_DIR / "bug-report.yml")

        # Assert
        assert form.title == "[Bug]: "
        assert form.labels == ("bug",)
        assert [field.kind for field in form.fields] == [
            FieldKind.TEXTAREA,
            FieldKind.TEXTAREA,
            FieldKind.TEXTAREA,
            FieldKind.DROPDOWN,
            FieldKind.CHECKBOXES,
        ]

    def test_a_label_loses_the_trailing_space_upstream_leaves_in_it(
        self, worktree: Path
    ):
        # Act
        form = load_form(worktree / TEMPLATE_DIR / "bug-report.yml")

        # Assert
        assert form.fields[2].label == VERSION

    def test_config_yml_configures_the_chooser_and_is_not_a_form(self, worktree: Path):
        # Act / Assert
        assert template_names(worktree) == ("bug-report",)

    def test_a_broken_form_names_its_file(self, tmp_path: Path):
        # Arrange
        path = tmp_path / "broken.yml"
        path.write_text("body: [unclosed\n")

        # Act / Assert
        with pytest.raises(PreconditionError, match=r"broken\.yml"):
            load_form(path)


class TestTheDraft:
    @pytest.fixture
    def draft(self, worktree: Path) -> str:
        form = load_form(worktree / TEMPLATE_DIR / "bug-report.yml")
        return render_draft(form, {VERSION: "```text\ncjc 1.0\n```"})

    def test_it_has_one_section_per_field_with_the_title_prefix_on_top(
        self, draft: str
    ):
        # Assert
        assert draft.startswith("# [Bug]: \n")
        assert f"### {WHAT}\n" in draft
        assert f"### {BRANCHES}\n" in draft

    def test_descriptions_are_comments_with_the_entities_decoded(self, draft: str):
        # Assert: the web form shows `|`, so the draft must too.
        assert "<!-- Required. 提供尽可能多的信息 | Provide" in draft

    def test_choices_are_task_items(self, draft: str):
        # Assert
        assert "- [ ] dev\n- [ ] main\n" in draft
        assert "- [ ] Tools\n- [ ] LSP\n" in draft

    def test_the_version_is_prefilled(self, draft: str):
        # Assert
        assert "cjc 1.0" in draft

    def test_the_version_field_is_found_by_its_label(self, worktree: Path):
        # Arrange
        form = load_form(worktree / TEMPLATE_DIR / "bug-report.yml")

        # Act
        field = version_field(form)

        # Assert
        assert field is not None
        assert field.label == VERSION


class TestReadingItBack:
    @pytest.fixture
    def form(self, worktree: Path):
        return load_form(worktree / TEMPLATE_DIR / "bug-report.yml")

    @pytest.fixture
    def complete(self, form) -> str:
        draft = render_draft(form, {VERSION: "cjc 1.0"})
        return filled(
            draft,
            **{
                "# [Bug]: ": "# [Bug]: sema crashes",
                f"### {WHAT}\n": f"### {WHAT}\nIt crashes.\n",
                "- [ ] main": "- [x] main",
            },
        )

    def test_a_complete_draft_becomes_a_title_and_a_body(self, form, complete: str):
        # Act
        title, body = read_draft(form, complete)

        # Assert
        assert title == "[Bug]: sema crashes"
        assert f"### {WHAT}\n\nIt crashes." in body
        assert "- [x] main" in body

    def test_comments_are_not_sent(self, form, complete: str):
        # Act
        _, body = read_draft(form, complete)

        # Assert
        assert "<!--" not in body

    def test_an_empty_optional_field_reads_as_no_response(self, form, complete: str):
        # Act
        _, body = read_draft(form, complete)

        # Assert
        assert f"### {EXTRA}\n\n{NO_RESPONSE}" in body

    def test_a_dropdown_sends_the_ticked_choice_not_the_list(self, form, complete):
        # Arrange
        draft = complete.replace("- [ ] LSP", "- [x] LSP")

        # Act
        _, body = read_draft(form, draft)

        # Assert
        assert "### 领域 | Domain\n\nLSP" in body

    def test_an_empty_required_field_is_refused_by_name(self, form, complete: str):
        # Arrange
        draft = complete.replace("It crashes.", "")

        # Act / Assert
        with pytest.raises(DraftError, match="Describe the issue"):
            read_draft(form, draft)

    def test_a_required_checkbox_list_needs_a_tick(self, form, complete: str):
        # Arrange
        draft = complete.replace("- [x] main", "- [ ] main")

        # Act / Assert
        with pytest.raises(DraftError, match="Branch version information"):
            read_draft(form, draft)

    def test_a_deleted_required_section_is_refused_too(self, form, complete: str):
        # Arrange
        draft = complete.replace(f"### {WHAT}\n", "")

        # Act / Assert
        with pytest.raises(DraftError):
            read_draft(form, draft)

    def test_the_bare_prefix_is_not_a_title(self, form, complete: str):
        # Arrange
        draft = complete.replace("# [Bug]: sema crashes", "# [Bug]: ")

        # Act / Assert
        with pytest.raises(DraftError, match="title"):
            read_draft(form, draft)

    def test_a_heading_that_is_no_label_stays_in_the_field(self, form, complete):
        # Arrange
        draft = complete.replace("It crashes.", "It crashes.\n### Backtrace\nframe 0")

        # Act
        _, body = read_draft(form, draft)

        # Assert
        assert "It crashes.\n### Backtrace\nframe 0" in body
