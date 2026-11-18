"""Reading a project's `.gitcode/ISSUE_TEMPLATE/*.yml` into an `IssueForm`.

YAML stays here the way TOML stays in `config.py`: nothing past this module
sees a parsed document, only the domain types.
"""

from pathlib import Path

import yaml

from cjdev.application.ports import Command, Executor
from cjdev.domain.issue_form import Choice, FieldKind, FormField, IssueForm
from cjdev.errors import PreconditionError

TEMPLATE_DIR = Path(".gitcode") / "ISSUE_TEMPLATE"

_NOT_FORMS = ("config",)
"""`config.yml` (and `config_en.yml`) configure the chooser, not a form."""


def template_names(worktree: Path) -> tuple[str, ...]:
    directory = worktree / TEMPLATE_DIR
    if not directory.is_dir():
        return ()
    return tuple(
        sorted(
            path.stem
            for path in directory.glob("*.yml")
            if not path.stem.startswith(_NOT_FORMS)
        )
    )


def load_form(path: Path) -> IssueForm:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        return _form(document)
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        raise PreconditionError(f"{path} is not a readable issue form: {exc}") from None


def parse_form(text: str) -> IssueForm:
    try:
        return _form(yaml.safe_load(text))
    except (yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        raise PreconditionError(f"cannot read issue form: {exc}") from None


def _form(document: dict) -> IssueForm:
    fields = []
    for item in document["body"]:
        # The greeting the web form shows above the fields; the issue never
        # carries it.
        if item["type"] == "markdown":
            continue
        attributes = item.get("attributes", {})
        fields.append(
            FormField(
                kind=FieldKind(item["type"]),
                label=str(attributes["label"]).strip(),
                description=str(attributes.get("description") or ""),
                required=bool((item.get("validations") or {}).get("required")),
                choices=tuple(_choice(o) for o in attributes.get("options") or ()),
            )
        )
    labels = document.get("labels") or ()
    if isinstance(labels, str):
        labels = labels.split(",")
    return IssueForm(
        name=str(document.get("name") or ""),
        title=str(document.get("title") or ""),
        labels=tuple(str(label).strip() for label in labels),
        fields=tuple(fields),
    )


def _choice(option: object) -> Choice:
    # A dropdown lists bare strings, a checkbox list `{label, required}` maps.
    if isinstance(option, dict):
        return Choice(str(option["label"]), bool(option.get("required")))
    return Choice(str(option))


class UpstreamForms:
    """Read the default branch's issue forms before a task has a checkout."""

    def __init__(self, executor: Executor, store: Path) -> None:
        self.executor = executor
        self.store = store
        self.tree = f"refs/remotes/upstream/HEAD:{TEMPLATE_DIR.as_posix()}"

    def names(self) -> tuple[str, ...]:
        files = self._git("ls-tree", "--name-only", self.tree)
        return tuple(
            sorted(
                name[:-4]
                for name in files.splitlines()
                if name.endswith(".yml") and not name.startswith(_NOT_FORMS)
            )
        )

    def load(self, name: str) -> IssueForm:
        return parse_form(self._git("show", f"{self.tree}/{name}.yml"))

    def _git(self, *args: str) -> str:
        command = Command(("git", *args), self.store, mutates=False)
        return self.executor.run(command).stdout
