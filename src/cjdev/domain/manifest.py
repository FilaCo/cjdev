"""The project set and the build-unit graph.

Manifest data, not code: the six projects, their remotes and the dependency
edges between build units all arrive from TOML (CFG-2) and are parsed into
these types at the `infra/` boundary. Nothing here touches the outside world.

The distinction §2 draws is the one to keep straight: a **project** is one git
repository - the unit of cloning, branching and PR creation - while a **build
unit** is one buildable subproject inside it. `cangjie_runtime` holds two. The
dependency graph is over units, never over projects.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum, auto, unique
from pathlib import PurePosixPath
from typing import final

from cjdev.errors import ManifestError


@final
@unique
class ProjectRole(Enum):
    """What a project contributes to the SDK.

    `TEST_RUNNER` and `TEST_DATA` build nothing (§4.3); they are cloned,
    branched and shipped like any other project, and simply own no build units.
    """

    BUILDABLE = auto()
    TEST_RUNNER = auto()
    TEST_DATA = auto()


@final
@dataclass(frozen=True)
class Project:
    name: str
    """The repository name, e.g. `cangjie_compiler`."""
    role: ProjectRole
    upstream_url: str
    default_branch: str
    """Detected per project, never hardcoded (SYNC-8). Manifest data even
    though every project happens to be `main` today."""


@final
@dataclass(frozen=True)
class BuildUnit:
    name: str
    """The token a user types: `stdlib`, not `cangjie_runtime/stdlib`.

    Flat and unique across the manifest, which `_reject_duplicates` enforces,
    so that the identifier in the code, in the manifest and on the command
    line is one string. Which project holds it is `project` below.
    """
    project: str
    path: PurePosixPath
    """Where the unit's own `build.py` lives, relative to the project
    worktree. `.` when the unit sits at the project root."""
    depends_on: tuple[str, ...]


@final
@dataclass(frozen=True)
class Manifest:
    """The whole project set. Declaration order is significant.

    Manifest order is the tie-break for every ordering `cjdev` produces -
    build order, status rows, the summary table - so that output does not
    depend on scheduling once commands fan out (PAR-4).
    """

    schema_version: int
    projects: tuple[Project, ...]
    build_units: tuple[BuildUnit, ...]
    groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    """Named subsets of the project set, for `--only` and friends (BRANCH-7)."""
    default_group: str | None = None
    """Which group a command offers when the user has expressed no preference.
    Manifest data rather than a constant, so that a workspace can decide the
    SDK it cares about without patching `cjdev` (CFG-2)."""

    def __post_init__(self) -> None:
        self._reject_duplicates()
        self._reject_dangling_references()
        self._reject_unknown_group_members()

    def group(self, name: str) -> tuple[Project, ...]:
        if name not in self.groups:
            known = ", ".join(sorted(self.groups)) or "none"
            raise ManifestError(f"unknown group {name}. Known groups: {known}.")
        members = set(self.groups[name])
        return tuple(p for p in self.projects if p.name in members)

    def default_projects(self) -> tuple[Project, ...]:
        """Every project when the manifest names no default group."""
        if self.default_group is None:
            return self.projects
        return self.group(self.default_group)

    def project(self, name: str) -> Project:
        for project in self.projects:
            if project.name == name:
                return project
        raise ManifestError(
            f"unknown project {name}. Known projects: {self._project_names()}."
        )

    def unit(self, name: str) -> BuildUnit:
        for unit in self.build_units:
            if unit.name == name:
                return unit
        raise ManifestError(
            f"unknown build unit {name}. Known units: {self._unit_names()}."
        )

    def units_of(self, name: str) -> tuple[BuildUnit, ...]:
        """Every unit the project holds, in manifest order.

        Empty for a project that builds nothing, and - until question A is
        answered - for one whose edges are simply not established yet (R11).
        Naming a project on the command line selects exactly this (BUILD-2).
        """
        self.project(name)
        return tuple(unit for unit in self.build_units if unit.project == name)

    def build_order(
        self, selection: Iterable[str] | None = None
    ) -> tuple[BuildUnit, ...]:
        """The selection plus everything it depends on, in dependency order.

        This is `--upto` (BUILD-2) and, with no selection, the whole-SDK build
        of BUILD-1. Ties are broken by manifest order, so the sequence is
        reproducible run to run.
        """
        wanted = self._with_dependencies(selection)
        position = {unit.name: i for i, unit in enumerate(self.build_units)}
        pending = sorted(wanted, key=lambda unit: position[unit.name])

        ordered: list[BuildUnit] = []
        satisfied: set[str] = set()
        while pending:
            ready = [
                unit
                for unit in pending
                if all(dep in satisfied for dep in unit.depends_on)
            ]
            if not ready:
                stuck = ", ".join(unit.name for unit in pending)
                raise ManifestError(f"dependency cycle among build units: {stuck}.")
            ordered.extend(ready)
            satisfied.update(unit.name for unit in ready)
            pending = [unit for unit in pending if unit.name not in satisfied]
        return tuple(ordered)

    def dependents_of(self, name: str) -> tuple[BuildUnit, ...]:
        """The unit and everything that transitively depends on it (`--from`).

        Returned in build order, so the result is directly runnable.
        """
        reached = {self.unit(name).name}
        changed = True
        while changed:
            changed = False
            for unit in self.build_units:
                if unit.name in reached:
                    continue
                if any(dep in reached for dep in unit.depends_on):
                    reached.add(unit.name)
                    changed = True
        return self.build_order(reached)

    def _reject_duplicates(self) -> None:
        self._reject_repeats("project", [p.name for p in self.projects])
        self._reject_repeats("build unit", [u.name for u in self.build_units])

    @staticmethod
    def _reject_repeats(what: str, names: list[str]) -> None:
        seen: set[str] = set()
        for name in names:
            if name in seen:
                raise ManifestError(f"{what} {name} is declared more than once.")
            seen.add(name)

    def _reject_dangling_references(self) -> None:
        projects = {project.name for project in self.projects}
        units = {unit.name for unit in self.build_units}
        for unit in self.build_units:
            if unit.project not in projects:
                raise ManifestError(
                    f"build unit {unit.name} belongs to unknown project "
                    f"{unit.project}. Known projects: {self._project_names()}."
                )
            for dep in unit.depends_on:
                if dep not in units:
                    raise ManifestError(
                        f"build unit {unit.name} depends on unknown unit "
                        f"{dep}. Known units: {self._unit_names()}."
                    )
                if dep == unit.name:
                    raise ManifestError(f"build unit {unit.name} depends on itself.")

    def _reject_unknown_group_members(self) -> None:
        known = {project.name for project in self.projects}
        for group, members in self.groups.items():
            for member in members:
                if member not in known:
                    raise ManifestError(
                        f"group {group} lists unknown project {member}. "
                        f"Known projects: {self._project_names()}."
                    )
        if self.default_group is not None and self.default_group not in self.groups:
            known_groups = ", ".join(sorted(self.groups)) or "none"
            raise ManifestError(
                f"default_group {self.default_group} is not a declared group. "
                f"Known groups: {known_groups}."
            )

    def _with_dependencies(self, selection: Iterable[str] | None) -> list[BuildUnit]:
        if selection is None:
            return list(self.build_units)
        reached: set[str] = set()
        frontier = [self.unit(name) for name in selection]
        while frontier:
            unit = frontier.pop()
            if unit.name in reached:
                continue
            reached.add(unit.name)
            frontier.extend(self.unit(dep) for dep in unit.depends_on)
        return [unit for unit in self.build_units if unit.name in reached]

    def _project_names(self) -> str:
        return ", ".join(project.name for project in self.projects)

    def _unit_names(self) -> str:
        return ", ".join(unit.name for unit in self.build_units)
