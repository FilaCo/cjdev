"""Reading the manifest, and the schema-version gate.

This is the boundary the CONTRIBUTING rule names: `tomlkit` types stop here.
Everything above receives `domain/` dataclasses.
"""

from importlib.resources import files
from pathlib import PurePosixPath
from typing import Any

import tomlkit

from cjdev.domain.manifest import BuildUnit, Manifest, Project, ProjectRole
from cjdev.errors import ManifestError

SUPPORTED_SCHEMA_VERSION = 1

BUNDLED_MANIFEST = "default_manifest.toml"

_ROLES = {
    "buildable": ProjectRole.BUILDABLE,
    "test_runner": ProjectRole.TEST_RUNNER,
    "test_data": ProjectRole.TEST_DATA,
}


def load_bundled_manifest() -> Manifest:
    """The manifest that ships in the wheel.

    Reached through `importlib.resources` rather than `__file__` so that it is
    found in an installed wheel and not only in a source checkout.
    """
    resource = files("cjdev.infra") / "data" / BUNDLED_MANIFEST
    return parse_manifest(resource.read_text(encoding="utf-8"), source=BUNDLED_MANIFEST)


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
            for name, body in _require(document, "projects", source).items()
        ),
        build_units=tuple(
            _build_unit(name, body, source)
            for name, body in document.get("build_units", {}).items()
        ),
        groups={
            name: tuple(str(member) for member in members)
            for name, members in document.get("groups", {}).items()
        },
        default_group=(
            str(document["default_group"]) if "default_group" in document else None
        ),
    )


def _project(name: str, body: Any, source: str) -> Project:
    where = f"{source}: project {name}"
    _reject_unknown_keys(body, {"role", "upstream", "default_branch"}, where)
    role = str(_require(body, "role", where))
    if role not in _ROLES:
        raise ManifestError(
            f"{source}: project {name} has unknown role {role!r}. "
            f"Known roles: {', '.join(sorted(_ROLES))}."
        )
    return Project(
        name=name,
        role=_ROLES[role],
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


WORKSPACE_CONFIG_TEMPLATE = """\
# cjdev workspace configuration.
#
# Everything here overrides a built-in default, so an empty file is a valid
# workspace. `cjdev config show --origin` prints the effective values and the
# layer each one came from.
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
