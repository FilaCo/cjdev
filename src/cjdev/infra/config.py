"""Reading the manifest, the workspace's overrides, and the schema-version gate.

This is the boundary the TOML rule in docs/architecture.md names: `tomlkit` types
stop here. Everything above receives `domain/` dataclasses.
"""

from importlib.resources import files
from pathlib import PurePosixPath
from typing import Any

import tomlkit

from cjdev.domain.config import (
    BUNDLED_MANIFEST,
    ROLE_NAMES,
    ProjectOverride,
    UnitOverride,
    WorkspaceConfig,
)
from cjdev.domain.manifest import BuildUnit, Manifest, Project
from cjdev.errors import ManifestError

SUPPORTED_SCHEMA_VERSION = 1

WORKSPACE_CONFIG = "config.toml"


def load_bundled_manifest() -> Manifest:
    """The manifest that ships in the wheel.

    Reached through `importlib.resources` rather than `__file__` so that it is
    found in an installed wheel and not only in a source checkout.
    """
    resource = files("cjdev.infra") / "data" / BUNDLED_MANIFEST
    return parse_manifest(resource.read_text(encoding="utf-8"), source=BUNDLED_MANIFEST)


def load_workspace_config(root: Any) -> WorkspaceConfig | None:
    """The workspace's own layer, read from `.cjdev/config.toml`.

    `Any` for the root rather than `Path`: this module has no business caring
    that the layout is more than a path, and the file lives under a marker the
    layout algebra derives. `None` when there is no workspace file - which is
    also what every non-workspace invocation gets, so the bundled manifest
    alone applies (FR-9's reading side).

    A file that `init` has not written yet but the user has created is real
    configuration all the same: existence is the gate, not provenance.
    """
    path = root / ".cjdev" / WORKSPACE_CONFIG
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # No workspace file is the ordinary shape here: every non-workspace
        # invocation lands on this arm, as does a fresh `init`.
        return None
    except (OSError, UnicodeDecodeError) as exc:
        # Everything else a read can raise - wrong permissions, a directory
        # where the file should be, bytes that are not UTF-8 - is a file a
        # human wrote by hand and wrote wrong. `main()` catches only
        # `CjdevError`, so these would reach the user as a traceback, and the
        # `--json` path would lose its envelope with them.
        raise ManifestError(f"cannot read {path}: {exc}") from exc
    return parse_workspace_config(text, source=WORKSPACE_CONFIG)


def parse_manifest(text: str, *, source: str) -> Manifest:
    try:
        document: Any = tomlkit.parse(text)
    except Exception as exc:  # tomlkit raises a family of parse errors
        raise ManifestError(f"{source} is not valid TOML: {exc}") from exc

    _reject_unknown_keys(
        document,
        {"schema_version", "default_group", "groups", "projects", "build_units"},
        source,
    )
    version = _require(document, "schema_version", source)
    if version != SUPPORTED_SCHEMA_VERSION:
        raise ManifestError(
            f"{source} declares schema_version {version}, but this cjdev "
            f"understands {SUPPORTED_SCHEMA_VERSION}. Upgrade cjdev, or pin "
            f"the manifest to schema_version {SUPPORTED_SCHEMA_VERSION}."
        )

    return Manifest(
        schema_version=int(version),
        projects=tuple(
            _project(name, body, source)
            for name, body in _require_table(
                document, "projects", source, required=True
            ).items()
        ),
        build_units=tuple(
            _build_unit(name, body, source)
            for name, body in _require_table(document, "build_units", source).items()
        ),
        groups=_groups(document, source),
        default_group=(
            str(document["default_group"]) if "default_group" in document else None
        ),
    )


def parse_workspace_config(text: str, *, source: str) -> WorkspaceConfig:
    """The workspace layer: everything optional, the gate still absolute.

    `schema_version` in the workspace file gets the same refusal as the
    bundled manifest's (FR-5) - a version this cjdev does not understand is
    refused with the upgrade message naming the workspace file. An absent one
    inherits the bundled version: today's template writes comments only, and
    the workspace layer is partial by design.
    """
    try:
        document: Any = tomlkit.parse(text)
    except Exception as exc:  # tomlkit raises a family of parse errors
        raise ManifestError(f"{source} is not valid TOML: {exc}") from exc

    _reject_unknown_keys(
        document,
        {"schema_version", "default_group", "groups", "projects", "build_units"},
        source,
    )
    version: int | None = None
    if "schema_version" in document:
        if document["schema_version"] != SUPPORTED_SCHEMA_VERSION:
            raise ManifestError(
                f"{source} declares schema_version {document['schema_version']}, "
                f"but this cjdev understands {SUPPORTED_SCHEMA_VERSION}. "
                f"Upgrade cjdev, or remove the key to inherit the bundled "
                f"manifest's version."
            )
        version = int(document["schema_version"])

    return WorkspaceConfig(
        source=source,
        schema_version=version,
        projects={
            name: _project_override(name, body, source)
            for name, body in _require_table(document, "projects", source).items()
        },
        build_units={
            name: _unit_override(name, body, source)
            for name, body in _require_table(document, "build_units", source).items()
        },
        groups=_groups(document, source),
        default_group=(
            str(document["default_group"]) if "default_group" in document else None
        ),
    )


def _project(name: str, body: Any, source: str) -> Project:
    """A bundled-manifest project: total, not partial."""
    where = f"{source}: project {name}"
    _reject_unknown_keys(body, {"role", "upstream", "default_branch"}, where)
    role = str(_require(body, "role", where))
    if role not in ROLE_NAMES:
        raise ManifestError(
            f"{source}: project {name} has unknown role {role!r}. "
            f"Known roles: {', '.join(sorted(ROLE_NAMES))}."
        )
    return Project(
        name=name,
        role=ROLE_NAMES[role],
        upstream_url=str(_require(body, "upstream", where)),
        default_branch=str(_require(body, "default_branch", where)),
    )


def _build_unit(name: str, body: Any, source: str) -> BuildUnit:
    where = f"{source}: build unit {name}"
    _reject_unknown_keys(body, {"project", "path", "depends_on"}, where)
    return BuildUnit(
        name=name,
        project=str(_require(body, "project", where)),
        path=PurePosixPath(str(_require(body, "path", where))),
        depends_on=tuple(str(dep) for dep in body.get("depends_on", [])),
    )


def _project_override(name: str, body: Any, source: str) -> ProjectOverride:
    where = f"{source}: project {name}"
    _reject_unknown_keys(body, {"role", "upstream", "default_branch"}, where)
    if not body:
        # Same refusal as `_unit_override`: a bare table header overrides
        # nothing, so honouring it would read as success while saying nothing
        # - almost always a key the user meant to write and forgot.
        raise ManifestError(
            f"{where} names no keys. Write what to override "
            f"(role, upstream, default_branch), or remove the table."
        )
    role = body.get("role")
    if role is not None and str(role) not in ROLE_NAMES:
        raise ManifestError(
            f"{where} has unknown role {str(role)!r}. "
            f"Known roles: {', '.join(sorted(ROLE_NAMES))}."
        )
    return ProjectOverride(
        role=ROLE_NAMES[str(role)] if role is not None else None,
        upstream=str(body["upstream"]) if "upstream" in body else None,
        default_branch=(
            str(body["default_branch"]) if "default_branch" in body else None
        ),
    )


def _unit_override(name: str, body: Any, source: str) -> UnitOverride:
    where = f"{source}: build unit {name}"
    _reject_unknown_keys(body, {"project", "path", "depends_on"}, where)
    if not body:
        # A bare table header overrides nothing, so honouring it would read as
        # success while saying nothing - almost always a key the user meant to
        # write and forgot. Refusing beats a silent shrug.
        raise ManifestError(
            f"{where} names no keys. Write what to override "
            f"(project, path, depends_on), or remove the table."
        )
    return UnitOverride(
        project=str(body["project"]) if "project" in body else None,
        path=PurePosixPath(str(body["path"])) if "path" in body else None,
        # `None` when the key is absent: an omitted `depends_on` inherits and
        # an explicit `[]` detaches, so the two must not read the same here.
        depends_on=(
            tuple(str(dep) for dep in body["depends_on"])
            if "depends_on" in body
            else None
        ),
    )


def _reject_unknown_keys(body: Any, allowed: set[str], where: str) -> None:
    """A key in the wrong place is the failure mode TOML makes easy: written
    after a table header it silently belongs to that table. Refusing what we
    do not understand turns that into a message instead of a shrug."""
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise ManifestError(
            f"{where} has unknown key(s) {', '.join(unknown)}. "
            f"Expected: {', '.join(sorted(allowed))}."
        )


def _require(body: Any, key: str, where: str) -> Any:
    if key not in body:
        raise ManifestError(f"{where} is missing required key {key!r}.")
    return body[key]


def _require_table(
    document: Any, key: str, source: str, *, required: bool = False
) -> Any:
    """The table `key` names, or an empty one when it is absent.

    The type is checked here, where `tomlkit` types still flow: a string or
    an array in a table's place is otherwise an `AttributeError` at the first
    `.items()` - not a `CjdevError`, so it would reach the user as a
    traceback instead of a refusal naming the key.
    """
    if key not in document:
        if required:
            raise ManifestError(f"{source} is missing required key {key!r}.")
        return {}
    table = document[key]
    if not isinstance(table, dict):
        raise ManifestError(
            f"{source}: {key} must be a table, not {type(table).__name__}."
        )
    return table


def _groups(document: Any, source: str) -> dict[str, tuple[str, ...]]:
    """Group members, with the array checked where the file is read: a string
    instead of an array would be iterated one character at a time, and the
    one-letter "projects" it yields fail far from the line that caused them."""
    groups: dict[str, tuple[str, ...]] = {}
    for name, members in _require_table(document, "groups", source).items():
        if not isinstance(members, list):
            raise ManifestError(
                f"{source}: group {name} must be an array of project names, "
                f"not {type(members).__name__}."
            )
        groups[name] = tuple(str(member) for member in members)
    return groups


WORKSPACE_CONFIG_TEMPLATE = """\
# cjdev workspace configuration.
#
# Everything here overrides the bundled manifest, so an empty file is a valid
# workspace: missing keys inherit the default. `cjdev config show` prints the
# effective result, and `-v` adds which layer every value came from.
"""


def render_workspace_config() -> str:
    """The starting config, comments and all.

    Rendered through `tomlkit` rather than returned as a literal because the
    user edits this file by hand and `cjdev config set` writes into it
    afterwards; a round trip that dropped their comments and reordered their
    keys would be the tool vandalising their file. Writing it is the caller's
    job, so that `--dry-run` can decline to.
    """
    return tomlkit.dumps(tomlkit.parse(WORKSPACE_CONFIG_TEMPLATE))
