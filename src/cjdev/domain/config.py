"""The two config layers, and the values each one contributed.

Two files describe the project set: the manifest bundled in the wheel and the
workspace's own `.cjdev/config.toml`. `layer` is the pure middle of that
composition: the bundled manifest and the parsed workspace file go in, the
effective `Manifest` comes out - alongside the same values carrying the layer
each came from, which is what `config show` renders and `--json` always carries.

The two layers are shaped differently, and the shape is the point. The bundled
manifest is total (`parse_manifest` refuses anything less); the workspace file
is partial by design - naming one field of one project must not require
restating that project's other fields, let alone every other project. So the
workspace side is `WorkspaceConfig`, whose `None`s mean "inherit from the layer
below" - and whose entries for names the bundled manifest has never heard of
must be complete, because there is nothing below to inherit from.

Removal is not something a workspace layer can do: v1 layers add and override,
and never drop a bundled project or build unit.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Generic, TypeVar, cast, final

from cjdev.domain.manifest import BuildUnit, Manifest, Project, ProjectRole
from cjdev.errors import ManifestError

BUNDLED = "bundled"
WORKSPACE = "workspace"
"""The two layers a value can come from. `config show` prints these words and
the `--json` payload carries them; changing one is a contract change."""

BUNDLED_MANIFEST = "default_manifest.toml"
"""The base layer's file, as errors name it. Lives here rather than in `infra/`
because the layering errors below have to name it too, and `domain` may not
import from `infra`."""

ROLE_NAMES: Mapping[str, ProjectRole] = {
    "buildable": ProjectRole.BUILDABLE,
    "test_runner": ProjectRole.TEST_RUNNER,
    "test_data": ProjectRole.TEST_DATA,
}

T = TypeVar("T")


@final
@dataclass(frozen=True)
class Sourced(Generic[T]):
    """One effective value, and the layer it came from."""

    value: T
    layer: str


@final
@dataclass(frozen=True)
class ProjectOverride:
    """The workspace's say about one project, field by field.

    `None` inherits from the layer below. The fields carry the TOML spellings
    (`upstream`, not `upstream_url`) because this shape is what the parser
    produces and the layering consumes; the `Project` rename happens here,
    once, on the way to the effective manifest.
    """

    role: ProjectRole | None = None
    upstream: str | None = None
    default_branch: str | None = None


@final
@dataclass(frozen=True)
class UnitOverride:
    project: str | None = None
    path: PurePosixPath | None = None
    depends_on: tuple[str, ...] | None = None
    """`None` inherits from the layer below; an explicit `[]` is a real answer
    (it detaches the unit from everything it inherited)."""


@final
@dataclass(frozen=True)
class WorkspaceConfig:
    """One workspace's overrides, before anything is inherited.

    An empty instance is exactly what `init` writes: a comment-only file.
    `source` is the file the overrides were read from - not used to compose
    anything, but every refusal this module raises has to name it.
    """

    source: str = BUNDLED_MANIFEST
    schema_version: int | None = None
    projects: Mapping[str, ProjectOverride] = field(default_factory=dict)
    build_units: Mapping[str, UnitOverride] = field(default_factory=dict)
    groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    default_group: str | None = None


@final
@dataclass(frozen=True)
class ProjectLayers:
    name: str
    role: Sourced[ProjectRole]
    upstream_url: Sourced[str]
    default_branch: Sourced[str]


@final
@dataclass(frozen=True)
class UnitLayers:
    name: str
    project: Sourced[str]
    path: Sourced[PurePosixPath]
    depends_on: Sourced[tuple[str, ...]]


@final
@dataclass(frozen=True)
class GroupLayers:
    name: str
    members: Sourced[tuple[str, ...]]


@final
@dataclass(frozen=True)
class LayeredManifest:
    """The effective manifest, and where each value came from.

    `effective` is what every command acts on; the rest is the same answer
    annotated, for `config show` alone.
    """

    schema_version: Sourced[int]
    default_group: Sourced[str | None]
    projects: tuple[ProjectLayers, ...]
    build_units: tuple[UnitLayers, ...]
    groups: tuple[GroupLayers, ...]
    effective: Manifest


def layer(base: Manifest, override: WorkspaceConfig) -> LayeredManifest:
    """The workspace config over the bundled manifest.

    Manifest order survives the composition: an overridden project or build
    unit keeps its bundled position, and only what the workspace adds is
    appended, in its declaration order. Every ordering cjdev produces breaks
    that position as its tie-break, so an override must not be able to shuffle
    the deck.
    """
    projects = _layer_projects(base, override)
    units = _layer_units(base, override)
    groups, default_group = _layer_groups(base, override)
    schema_version = (
        Sourced(override.schema_version, WORKSPACE)
        if override.schema_version is not None
        else Sourced(base.schema_version, BUNDLED)
    )
    _reject_dangling(override, projects, units, groups, default_group)
    effective = Manifest(
        schema_version=schema_version.value,
        projects=tuple(
            Project(
                name=entry.name,
                role=entry.role.value,
                upstream_url=entry.upstream_url.value,
                default_branch=entry.default_branch.value,
            )
            for entry in projects
        ),
        build_units=tuple(
            BuildUnit(
                name=unit.name,
                project=unit.project.value,
                path=unit.path.value,
                depends_on=unit.depends_on.value,
            )
            for unit in units
        ),
        groups={g.name: g.members.value for g in groups},
        default_group=default_group.value,
    )
    # A cycle through the two layers is refused here rather than at the first
    # `build_order`: the refusal has to name the config files that combined
    # into it, and it has to happen at load time, not when a command happens
    # to order a build days later.
    effective.build_order()
    return LayeredManifest(
        schema_version=schema_version,
        default_group=default_group,
        projects=projects,
        build_units=units,
        groups=groups,
        effective=effective,
    )


def _layer_projects(
    base: Manifest, override: WorkspaceConfig
) -> tuple[ProjectLayers, ...]:
    layered = [
        ProjectLayers(
            name=project.name,
            role=_field(
                project.role, o is not None and o.role is not None, o and o.role
            ),
            upstream_url=_field(
                project.upstream_url,
                o is not None and o.upstream is not None,
                o and o.upstream,
            ),
            default_branch=_field(
                project.default_branch,
                o is not None and o.default_branch is not None,
                o and o.default_branch,
            ),
        )
        for project in base.projects
        for o in (override.projects.get(project.name),)
    ]
    for name, o in override.projects.items():
        if name in {p.name for p in base.projects}:
            continue
        missing = [
            key
            for key, value in (
                ("role", o.role),
                ("upstream", o.upstream),
                ("default_branch", o.default_branch),
            )
            if value is None
        ]
        if missing:
            raise ManifestError(
                f"{override.source}: project {name} must declare role, upstream "
                f"and default_branch - the bundled manifest does not know it, so "
                f"there is nothing to inherit. Missing: {', '.join(missing)}."
            )
        layered.append(
            ProjectLayers(
                name=name,
                # The completeness check above has narrowed these to non-None:
                # a project the bundled manifest has never heard of must
                # declare every field.
                role=Sourced(cast(ProjectRole, o.role), WORKSPACE),
                upstream_url=Sourced(cast(str, o.upstream), WORKSPACE),
                default_branch=Sourced(cast(str, o.default_branch), WORKSPACE),
            )
        )
    return tuple(layered)


def _layer_units(base: Manifest, override: WorkspaceConfig) -> tuple[UnitLayers, ...]:
    layered = [
        UnitLayers(
            name=unit.name,
            project=_field(
                unit.project,
                o is not None and o.project is not None,
                o and o.project,
            ),
            path=_field(unit.path, o is not None and o.path is not None, o and o.path),
            depends_on=_field(
                unit.depends_on,
                o is not None and o.depends_on is not None,
                o and o.depends_on,
            ),
        )
        for unit in base.build_units
        for o in (override.build_units.get(unit.name),)
    ]
    for name, o in override.build_units.items():
        if name in {u.name for u in base.build_units}:
            continue
        # An added unit's dependencies default to none rather than being
        # required: a project can land in a workspace before its edges do,
        # which is exactly how the bundled manifest treats interop.
        if o.project is None or o.path is None:
            missing = [
                key
                for key, value in (("project", o.project), ("path", o.path))
                if value is None
            ]
            raise ManifestError(
                f"{override.source}: build unit {name} must declare project and "
                f"path - the bundled manifest does not know it, so there is "
                f"nothing to inherit. Missing: {', '.join(missing)}."
            )
        layered.append(
            UnitLayers(
                name=name,
                # The completeness check above has narrowed these to non-None.
                project=Sourced(o.project, WORKSPACE),
                path=Sourced(o.path, WORKSPACE),
                depends_on=Sourced(o.depends_on or (), WORKSPACE),
            )
        )
    return tuple(layered)


def _layer_groups(
    base: Manifest, override: WorkspaceConfig
) -> tuple[tuple[GroupLayers, ...], Sourced[str | None]]:
    """Groups merge by name: a workspace redeclaring one replaces it whole.

    Member-by-member merging would invent append semantics nothing asked for;
    replacing the list is what "override" says.
    """
    groups = [
        GroupLayers(
            name=name,
            members=(
                Sourced(override.groups[name], WORKSPACE)
                if name in override.groups
                else Sourced(members, BUNDLED)
            ),
        )
        for name, members in base.groups.items()
    ] + [
        GroupLayers(name=name, members=Sourced(members, WORKSPACE))
        for name, members in override.groups.items()
        if name not in base.groups
    ]
    default_group: Sourced[str | None] = (
        Sourced(override.default_group, WORKSPACE)
        if override.default_group is not None
        else Sourced(base.default_group, BUNDLED)
    )
    return tuple(groups), default_group


def _field(bundled: T, overridden: bool, value: T | None) -> Sourced[T]:
    """One effective field: the override's value when there is one, else the
    layer below's - with the provenance to tell them apart."""
    if overridden and value is not None:
        return Sourced(value, WORKSPACE)
    return Sourced(bundled, BUNDLED)


def _reject_dangling(
    override: WorkspaceConfig,
    projects: tuple[ProjectLayers, ...],
    units: tuple[UnitLayers, ...],
    groups: tuple[GroupLayers, ...],
    default_group: Sourced[str | None],
) -> None:
    """Cross-references are checked on the effective result, not per file.

    Two individually valid layers can still combine into a dangling reference,
    so the check runs after the merge. The error names the layer that
    introduced the dangling name: with two files in play, a refusal that just
    says "the manifest" names nothing.
    """
    where = {BUNDLED: BUNDLED_MANIFEST, WORKSPACE: override.source}
    known_projects = {project.name for project in projects}
    known_units = {unit.name for unit in units}

    for unit in units:
        if unit.project.value not in known_projects:
            raise ManifestError(
                f"{where[unit.project.layer]}: build unit {unit.name} belongs to "
                f"unknown project {unit.project.value}. Known projects: "
                f"{', '.join(sorted(known_projects))}."
            )
        for dep in unit.depends_on.value:
            if dep not in known_units:
                raise ManifestError(
                    f"{where[unit.depends_on.layer]}: build unit {unit.name} "
                    f"depends on unknown unit {dep}. Known units: "
                    f"{', '.join(sorted(known_units))}."
                )
            if dep == unit.name:
                raise ManifestError(
                    f"{where[unit.depends_on.layer]}: build unit {unit.name} "
                    f"depends on itself."
                )

    for group in groups:
        for member in group.members.value:
            if member not in known_projects:
                raise ManifestError(
                    f"{where[group.members.layer]}: group {group.name} lists "
                    f"unknown project {member}. Known projects: "
                    f"{', '.join(sorted(known_projects))}."
                )

    if default_group.value is not None and default_group.value not in {
        group.name for group in groups
    }:
        known_groups = ", ".join(sorted(group.name for group in groups)) or "none"
        raise ManifestError(
            f"{where[default_group.layer]}: default_group {default_group.value} "
            f"is not a declared group. Known groups: {known_groups}."
        )
