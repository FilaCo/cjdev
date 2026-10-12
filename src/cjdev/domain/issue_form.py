"""A GitCode issue form, the Markdown draft cjdev renders from it, and the
issue read back out of that draft.

The forge does not enforce the form: the API takes free Markdown, so the
required-field check is entirely ours, and it happens here, before anything
is sent.
"""

import html
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from typing import final

from cjdev.errors import DraftError


@final
@unique
class FieldKind(Enum):
    TEXTAREA = "textarea"
    INPUT = "input"
    DROPDOWN = "dropdown"
    CHECKBOXES = "checkboxes"


@final
@dataclass(frozen=True)
class Choice:
    label: str
    required: bool = False


@final
@dataclass(frozen=True)
class FormField:
    kind: FieldKind
    label: str
    description: str = ""
    required: bool = False
    choices: tuple[Choice, ...] = ()

    @property
    def is_choice(self) -> bool:
        return self.kind in (FieldKind.DROPDOWN, FieldKind.CHECKBOXES)


@final
@dataclass(frozen=True)
class IssueForm:
    name: str
    title: str
    """The prefix the title starts with, `[Bug]: `."""
    labels: tuple[str, ...]
    fields: tuple[FormField, ...]


NO_RESPONSE = "_No response_"
"""What an empty optional field reads as, the way the web form sends it."""

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_TICKED = re.compile(r"^\s*[-*] \[[xX]\] (.+?)\s*$")


def version_field(form: IssueForm) -> FormField | None:
    """The field that asks for `cjc -v`. Found by its label, which every
    upstream bug form spells with `cjc` in one language or the other."""
    for field in form.fields:
        if field.kind is FieldKind.TEXTAREA and "cjc" in field.label.lower():
            return field
    return None


def render_draft(form: IssueForm, prefill: Mapping[str, str]) -> str:
    """One `###` section per field, keyed by label; `prefill` maps a label to
    its starting text."""
    lines = [
        f"# {form.title}",
        _comment(f"{form.name}. Comments are dropped before sending."),
    ]
    for field in form.fields:
        hint = ("Required. " if field.required else "") + field.description
        lines += ["", f"### {field.label}", _comment(hint), ""]
        if field.is_choice:
            lines += [f"- [ ] {choice.label}" for choice in field.choices]
        elif prefill.get(field.label):
            lines.append(prefill[field.label])
    return "\n".join(lines) + "\n"


def read_draft(form: IssueForm, text: str) -> tuple[str, str]:
    """The title and body of a filled draft, or a refusal naming the field
    that is missing."""
    by_label = {field.label: field for field in form.fields}
    title = ""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in _COMMENT.sub("", text).splitlines():
        heading = line[4:].strip() if line.startswith("### ") else None
        if heading in by_label:
            current = heading
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
        elif line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.strip():
            raise DraftError(f"text outside any field: {line.strip()!r}.")

    if not title or title == form.title.strip():
        raise DraftError("the title is empty.")
    values = {label: "\n".join(lines).strip() for label, lines in sections.items()}
    body = [_section(field, values.get(field.label, "")) for field in form.fields]
    return title, "\n\n".join(body) + "\n"


def _section(field: FormField, value: str) -> str:
    if field.is_choice:
        ticked = [
            m.group(1) for line in value.splitlines() if (m := _TICKED.match(line))
        ]
        missing = [
            c.label for c in field.choices if c.required and c.label not in ticked
        ]
        if (field.required and not ticked) or missing:
            raise DraftError(f'"{field.label}" needs a ticked choice.')
        if field.kind is FieldKind.DROPDOWN:
            value = ", ".join(ticked)
    elif field.required and not value:
        raise DraftError(f'"{field.label}" is required and empty.')
    return f"### {field.label}\n\n{value or NO_RESPONSE}"


def _comment(text: str) -> str:
    # Descriptions arrive with `&#124;` where the web form shows `|`, and a
    # literal `-->` would end the comment early and send the rest.
    return f"<!-- {html.unescape(text).replace('-->', '- ->')} -->"
