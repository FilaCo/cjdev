"""Building the SDK: one unit at a time, keyed by profile.

Three things make this more than "run the script in the worktree".

**No upstream script takes a flag for where its artefacts go.** Every one of
them derives its output directory from `__file__`, and wipes it, or walks up out
of it with `..`, on the assumption that it is a real directory in the worktree.
So it is one, for the length of the build: the profile's scratch directories
are moved in from `.cjdev/build/<set>/<env>/<profile>/` before the unit builds
and moved back after. Which paths are scratch is per unit and comes from the
manifest, because `build/` is tracked source in two of the projects.

**That makes a worktree stateful while a unit builds**, so a marker names the
profile whose scratch is in it, and a run that died before moving it back is
finished by the next one. All of it happens under a lock per (branch set, unit).

**Units do not overlap.** Each script already takes the whole machine, so
`Runner(jobs=1, fail_fast=True)` over `build_order()` is the schedule: at one
job the runner executes in submission order, and everything after a failure is
marked CANCELLED, which is the right word for a chain.
"""

import os
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import Enum, auto, unique
from pathlib import Path, PurePath, PurePosixPath
from typing import final

from cjdev.application.ports import Command, Executor, FileSystem
from cjdev.application.report_status import ManifestProvider
from cjdev.application.runner import Outcome, Runner, RunObserver, RunReport, Work
from cjdev.domain.build import (
    BUILD_DIR,
    DIST,
    JOBS,
    PROFILE,
    CopyStep,
    Host,
    Profile,
    RunStep,
    substitute,
)
from cjdev.domain.environment import DEFAULT_ENVIRONMENT, Environment, Mode
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import BuildUnit, Manifest
from cjdev.errors import PreconditionError, UsageError

HostProvider = Callable[[], Host]
"""What the environment contributes, read when the command runs rather than
when the composition root was built: under a container the image and the daemon
are what answer, and neither is reachable from a constructor."""

Lock = Callable[[PurePath], AbstractContextManager[None]]
"""Held for the whole of one unit's build. Not a port: it has one
implementation and a dry run's no-op, the way `jobs` has a default."""

EXCLUDE_HEADER = "# cjdev: build scratch"
"""What cjdev's own lines in an object store's `info/exclude` are marked with,
so a second run recognises them and a reader knows who wrote them."""

SHIMMED = ("clang", "clang++")
"""What the shim directory stands in for. `stdlib/build.py` overwrites `CC` and
`CXX` from its own `shutil.which`, so the launcher has to be something `which`
finds - and nothing upstream takes a cmake launcher flag."""


@final
@unique
class ScratchState(Enum):
    """What is at a scratch path in the worktree before a build."""

    ABSENT = auto()
    PRESENT = auto()
    """A real file or directory. Ours when the marker says a build left it
    there; otherwise somebody built here by hand, and it is a refusal."""
    LINKED = auto()
    """A symlink, which is what scratch was before it was moved instead."""


@final
@dataclass(frozen=True)
class Seen:
    scratch: PurePosixPath
    state: ScratchState
    target: PurePosixPath | None = None
    """Where a link points, to tell our old redirects from somebody's link."""


@final
@dataclass(frozen=True)
class Observed:
    scratch: Mapping[str, tuple[Seen, ...]]
    moved: Mapping[str, str]
    """Per unit, the marker of a build that has not moved its scratch back:
    `<environment>/<profile>`. Absent for a unit with nothing moved in."""
    excludes: Mapping[str, str]
    """One project's current `info/exclude`, empty when it has none."""
    worktrees: frozenset[str]


@final
@dataclass(frozen=True)
class Move:
    source: PurePath
    destination: PurePath


@final
@dataclass(frozen=True)
class Copy:
    source: PurePath
    into: PurePath


@final
@dataclass(frozen=True)
class Shim:
    link: PurePath
    target: PurePath


@final
@dataclass(frozen=True)
class Exclusion:
    """One object store's `info/exclude`, rewritten whole.

    Per project rather than per unit: `cangjie_runtime` holds two units, and
    two writes each computed from the same original text would lose the first
    one's lines.
    """

    path: PurePath
    text: str


Step = Command | Copy


@final
@dataclass(frozen=True)
class UnitPlan:
    unit: str
    project: str
    directory: PurePath
    log: PurePath
    lock: PurePath
    marker: PurePath
    moved: str
    stale: tuple[PurePath, ...]
    """Old redirect symlinks, removed before anything moves."""
    recover: tuple[Move, ...]
    """What a build that died left in the worktree, going back where it lives."""
    scratch: tuple[Move, ...]
    """Into the worktree before the build; reversed after it."""
    steps: tuple[Step, ...]


@final
@dataclass(frozen=True)
class BuildPlan:
    root: PurePath
    branch_set: str
    profile: Profile
    dist: PurePath
    directories: tuple[PurePath, ...]
    shims: tuple[Shim, ...]
    exclusions: tuple[Exclusion, ...]
    units: tuple[UnitPlan, ...]


@final
@dataclass(frozen=True)
class Built:
    """One unit's line in the report."""

    unit: str
    log: PurePath
    outcome: Outcome
    took: float | None = None
    error: Exception | None = None


@final
@dataclass(frozen=True)
class BuildReport:
    plan: BuildPlan
    rows: tuple[Built, ...]
    interrupted: bool = False

    @property
    def ok(self) -> bool:
        return not self.interrupted and all(
            row.outcome is Outcome.DONE for row in self.rows
        )

    @property
    def failures(self) -> tuple[Built, ...]:
        return tuple(row for row in self.rows if row.outcome is Outcome.FAILED)


def select_units(
    manifest: Manifest, names: Sequence[str], *, downstream: str | None = None
) -> tuple[BuildUnit, ...]:
    """The units to build, in dependency order.

    A name is a build unit or a project: naming a project selects every unit it
    holds, which is what makes `cjdev build cangjie_runtime` mean both of them.
    `downstream` is the other direction - the unit and everything that depends
    on it - and the two cannot be combined, because the result would depend on
    which was applied first.
    """
    units = {unit.name for unit in manifest.build_units}
    projects = {project.name for project in manifest.projects}
    if downstream is not None:
        if names:
            raise UsageError(
                "--from names where to start; positional units name where to "
                "stop. Use one or the other."
            )
        if downstream not in units:
            # Checked here rather than left to `dependents_of`: a mistyped name
            # is the invocation being wrong, and the manifest raising would
            # report it as the world not being ready - a different exit code
            # and a different `code` for the same typo the positional branch
            # below calls a usage error.
            raise UsageError(
                f"unknown build unit {downstream}. Units: {', '.join(sorted(units))}."
            )
        return manifest.dependents_of(downstream)
    if not names:
        return manifest.build_order()
    selection: list[str] = []
    for name in names:
        if name in units:
            selection.append(name)
            continue
        if name not in projects:
            raise UsageError(
                f"unknown build unit or project {name}. Units: "
                f"{', '.join(sorted(units))}. Projects: "
                f"{', '.join(sorted(projects))}."
            )
        held = manifest.units_of(name)
        if not held:
            raise UsageError(
                f"{name} holds no build units, so there is nothing to build."
            )
        selection.extend(unit.name for unit in held)
    return manifest.build_order(selection)


def observe(
    layout: WorkspaceLayout, branch_set: str, units: Sequence[BuildUnit]
) -> Observed:
    return Observed(
        scratch={
            unit.name: tuple(
                _seen(layout, branch_set, unit, scratch) for scratch in unit.scratch
            )
            for unit in units
        },
        moved={
            unit.name: marker
            for unit in units
            if (marker := _read(Path(layout.scratch_marker(branch_set, unit.name))))
        },
        excludes={
            unit.project: _read(
                Path(layout.object_store(unit.project)) / "info" / "exclude"
            )
            for unit in units
        },
        worktrees=frozenset(
            unit.project
            for unit in units
            if Path(layout.worktree(branch_set, unit.project)).is_dir()
        ),
    )


def decide(
    layout: WorkspaceLayout,
    branch_set: str,
    profile: Profile,
    units: Sequence[BuildUnit],
    host: Host,
    observed: Observed,
    *,
    environment: Environment = DEFAULT_ENVIRONMENT,
    passthrough: Sequence[str] = (),
) -> BuildPlan:
    """The whole run, settled before the first directory moves."""
    if passthrough and len(units) != 1:
        raise UsageError(
            f"arguments after `--` reach one build script, and this selection "
            f"resolves to {len(units)} units "
            f"({', '.join(unit.name for unit in units)}). Name one unit."
        )
    where = environment.mode.value
    dist = layout.dist_dir(branch_set, where, profile.value)
    planned = tuple(
        _unit_plan(
            layout, branch_set, where, profile, unit, host, observed, passthrough
        )
        for unit in units
    )
    exclusions = _exclusions(layout, units, observed)
    return BuildPlan(
        root=layout.root,
        branch_set=branch_set,
        profile=profile,
        dist=dist,
        directories=(
            dist,
            layout.log_dir(branch_set),
            *(
                ()
                if host.ccache is None
                else (layout.shim_dir(where), layout.ccache_dir)
            ),
            # The container is told to use a home inside the mount, because
            # the image has no passwd entry for the uid it runs as.
            *(() if environment.mode is Mode.HOST else (layout.home_dir,)),
            *(plan.marker.parent for plan in planned),
            # `write_text` writes one file and creates no directory, and a
            # store whose `info/` is missing is otherwise a FileNotFoundError
            # on the way into a build.
            *(exclusion.path.parent for exclusion in exclusions),
        ),
        shims=_shims(layout, where, host),
        exclusions=exclusions,
        units=planned,
    )


def report_rows(plan: BuildPlan, report: RunReport[float]) -> tuple[Built, ...]:
    """One row per unit, in build order rather than finish order.

    Built from the plan: a unit the run never reached has no result, and
    "cancelled" is what that means in a chain.
    """
    results = {result.label: result for result in report.results}
    rows = []
    for unit in plan.units:
        result = results.get(unit.unit)
        rows.append(
            Built(
                unit=unit.unit,
                log=unit.log,
                outcome=Outcome.CANCELLED if result is None else result.outcome,
                took=None if result is None else result.value,
                error=None if result is None else result.error,
            )
        )
    return tuple(rows)


def _unit_plan(
    layout: WorkspaceLayout,
    branch_set: str,
    where: str,
    profile: Profile,
    unit: BuildUnit,
    host: Host,
    observed: Observed,
    passthrough: Sequence[str],
) -> UnitPlan:
    if unit.project not in observed.worktrees:
        raise PreconditionError(
            f"{unit.project} has no worktree in branch set {branch_set}.",
            subject=unit.name,
            remedy=f"cjdev branch new {branch_set}",
        )
    if not unit.build:
        raise PreconditionError(
            f"no build command is recorded for {unit.name}.",
            subject=unit.name,
            remedy="write one in .cjdev/config.toml",
        )
    directory = layout.worktree(branch_set, unit.project) / unit.path
    log = layout.unit_log(branch_set, unit.name)
    env = build_environment(layout, branch_set, where, profile, host)
    values = {
        PROFILE: profile.value,
        JOBS: str(host.jobs),
        DIST: str(layout.dist_dir(branch_set, where, profile.value)),
        BUILD_DIR: str(layout.build_dir(branch_set, where, profile.value, unit.name)),
    }
    return UnitPlan(
        unit=unit.name,
        project=unit.project,
        directory=directory,
        log=log,
        lock=layout.build_lock(branch_set, unit.name),
        marker=layout.scratch_marker(branch_set, unit.name),
        moved=f"{where}/{profile.value}",
        stale=_stale(layout, branch_set, unit, observed),
        recover=_recover(layout, branch_set, unit, observed),
        scratch=tuple(
            Move(
                source=layout.scratch_dir(
                    branch_set, where, profile.value, unit.name, scratch
                ),
                destination=directory / scratch,
            )
            for scratch in unit.scratch
        ),
        steps=(
            Command(
                argv=(
                    *(
                        substitute(word, values)
                        for word in (*unit.build, *unit.extra_args)
                    ),
                    # Verbatim: what follows `--` is the caller's, and a brace
                    # in it is one the build script asked for rather than a
                    # token this has any business reading.
                    *passthrough,
                ),
                cwd=Path(directory),
                env=env,
                log=log,
                what=f"building {unit.name}",
            ),
            *(
                _install_step(step, directory, env, log, unit.name, values)
                for step in unit.install
            ),
        ),
    )


def _install_step(
    step: RunStep | CopyStep,
    directory: PurePath,
    env: Mapping[str, str],
    log: PurePath,
    unit: str,
    values: Mapping[str, str],
) -> Step:
    if isinstance(step, CopyStep):
        return Copy(
            source=directory / step.source,
            into=PurePath(substitute(step.into, values)),
        )
    return Command(
        argv=tuple(substitute(word, values) for word in step.argv),
        cwd=Path(directory),
        env=env,
        log=log,
        what=f"installing {unit}",
    )


def _stale(
    layout: WorkspaceLayout, branch_set: str, unit: BuildUnit, observed: Observed
) -> tuple[PurePath, ...]:
    """Redirect symlinks from before scratch was moved. Their targets are the
    directories a move uses, so removing the link loses nothing."""
    stale = []
    for seen in observed.scratch.get(unit.name, ()):
        if seen.state is not ScratchState.LINKED or seen.target is None:
            continue
        link = layout.worktree(branch_set, unit.project) / unit.path / seen.scratch
        resolved = PurePath(os.path.normpath(link.parent / seen.target))
        if not resolved.is_relative_to(layout.marker / "build"):
            raise PreconditionError(
                f"{link} is a symlink cjdev did not write; a build would write "
                f"through it.",
                subject=unit.name,
                remedy=f"remove {link}",
            )
        stale.append(link)
    return tuple(stale)


def _recover(
    layout: WorkspaceLayout, branch_set: str, unit: BuildUnit, observed: Observed
) -> tuple[Move, ...]:
    marker = observed.moved.get(unit.name)
    recover = []
    for seen in observed.scratch.get(unit.name, ()):
        if seen.state is not ScratchState.PRESENT:
            continue
        here = layout.worktree(branch_set, unit.project) / unit.path / seen.scratch
        if marker is None:
            raise PreconditionError(
                f"{here} is a real directory no cjdev build left there; moving "
                f"this profile's scratch in would mix the two.",
                subject=unit.name,
                remedy=f"move or delete {here}",
            )
        where, _, profile = marker.strip().partition("/")
        recover.append(
            Move(
                source=here,
                destination=layout.scratch_dir(
                    branch_set, where, profile, unit.name, seen.scratch
                ),
            )
        )
    return tuple(recover)


def build_environment(
    layout: WorkspaceLayout, branch_set: str, where: str, profile: Profile, host: Host
) -> dict[str, str]:
    """The SDK under construction, and the cache.

    Public because `cjdev env run` exists to reproduce a build step by hand,
    and a step run without the environment the build gave it is a different
    command that happens to share an argv.

    This is what `source <sdk>/envsetup.sh` does, derived from the layout
    instead: every unit after the compiler builds *with* the SDK the ones
    before it installed, and `stdlib`, `stdx` and `cjpm` all invoke `cjc` by
    name. Derived rather than declared in the manifest, because these
    directories are cjdev's own and a manifest naming them too would be a
    second place for them to disagree.
    """
    env = {
        "CANGJIE_HOME": str(layout.dist_dir(branch_set, where, profile.value)),
        "CANGJIE_STDX_PATH": str(
            layout.stdx_lib_dir(branch_set, where, profile.value, host.target)
        ),
        host.library_var: _joined(
            layout.sdk_library_path(branch_set, where, profile.value, host.target),
            host.library_path,
        ),
    }
    path = layout.sdk_path(branch_set, where, profile.value)
    if host.ccache is None:
        return env | {"PATH": _joined(path, host.path)}
    return env | {
        # BASEDIR is what makes one store serve every branch set: ccache hashes
        # absolute paths, so without it the same file in two sets never hits.
        # `hash_dir` off for the same reason - the price is debug info that may
        # name the other set's source.
        "CCACHE_DIR": str(layout.ccache_dir),
        "CCACHE_BASEDIR": str(layout.root),
        "CCACHE_NOHASHDIR": "1",
        # The shim goes in front of the SDK's own directories: it stands in for
        # the C compiler, which is not something the SDK provides.
        "PATH": _joined((layout.shim_dir(where), *path), host.path),
    }


def _joined(ours: tuple[PurePath, ...], theirs: str) -> str:
    """Ours first, then whatever the caller already had. An empty inherited
    value must not leave a trailing separator, which the shell reads as the
    current directory."""
    return os.pathsep.join(
        [*(str(path) for path in ours), *([theirs] if theirs else [])]
    )


def _shims(layout: WorkspaceLayout, where: str, host: Host) -> tuple[Shim, ...]:
    if host.ccache is None:
        return ()
    return tuple(
        Shim(link=layout.shim_dir(where) / name, target=host.ccache) for name in SHIMMED
    )


def _exclusions(
    layout: WorkspaceLayout, units: Sequence[BuildUnit], observed: Observed
) -> tuple[Exclusion, ...]:
    """The scratch paths, written into each object store's `info/exclude`.

    Two of the projects do not gitignore what their build writes, so without
    this the scratch a build leaves behind shows up as untracked: `cjdev
    status` calls the worktree dirty and `git worktree remove` refuses.
    `info/exclude` is shared by every worktree of a store, so one write covers
    every branch set, and no tracked file is touched.
    """
    exclusions = []
    for project in dict.fromkeys(unit.project for unit in units):
        current = observed.excludes.get(project, "")
        wanted = [
            f"/{unit.path / scratch}"
            for unit in units
            if unit.project == project
            for scratch in unit.scratch
        ]
        missing = [line for line in wanted if line not in current.splitlines()]
        if not missing:
            continue
        head = current if current.endswith("\n") or not current else current + "\n"
        # The header marks our lines for a reader; a second copy of it would
        # mark nothing and accumulate as the scratch set grows.
        marker = "" if EXCLUDE_HEADER in current.splitlines() else f"{EXCLUDE_HEADER}\n"
        exclusions.append(
            Exclusion(
                path=layout.object_store(project) / "info" / "exclude",
                text="".join([head, marker, *(f"{line}\n" for line in missing)]),
            )
        )
    return tuple(exclusions)


def _seen(
    layout: WorkspaceLayout, branch_set: str, unit: BuildUnit, scratch: PurePosixPath
) -> Seen:
    link = Path(layout.worktree(branch_set, unit.project) / unit.path / scratch)
    if link.is_symlink():
        return Seen(scratch, ScratchState.LINKED, PurePosixPath(link.readlink()))
    if link.exists():
        return Seen(scratch, ScratchState.PRESENT)
    return Seen(scratch, ScratchState.ABSENT)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError):
        return ""


@final
class BuildUnits:
    def __init__(
        self,
        manifest: ManifestProvider,
        executor: Executor,
        file_system: FileSystem,
        host: HostProvider,
        lock: Lock,
        environment: Environment = DEFAULT_ENVIRONMENT,
    ) -> None:
        # A provider rather than a Manifest: the workspace layer is resolved
        # when the command runs, from where the caller stands - not when the
        # composition root was built.
        self._manifest = manifest
        self._executor = executor
        self._fs = file_system
        self._host = host
        self._lock = lock
        self._environment = environment

    def plan(
        self,
        root: Path,
        branch_set: str,
        *,
        profile: Profile,
        names: Sequence[str] = (),
        downstream: str | None = None,
        passthrough: Sequence[str] = (),
    ) -> BuildPlan:
        """Everything `apply` would do, decided without doing any of it."""
        layout = WorkspaceLayout(root)
        units = select_units(self._manifest(), names, downstream=downstream)
        if not units:
            raise PreconditionError(
                "the manifest declares no build units, so there is nothing to build."
            )
        return decide(
            layout,
            branch_set,
            profile,
            units,
            # Gathered here rather than held since construction: under a
            # container this is a read of the daemon and the image.
            self._host(),
            observe(layout, branch_set, units),
            environment=self._environment,
            passthrough=passthrough,
        )

    def apply(
        self, plan: BuildPlan, *, observer: RunObserver | None = None
    ) -> BuildReport:
        for directory in _unique(plan.directories):
            self._fs.mkdir(directory)
        for shim in plan.shims:
            self._fs.symlink(shim.link, shim.target)
        for exclusion in plan.exclusions:
            self._fs.write_text(exclusion.path, exclusion.text)

        # One job, and fail_fast: the units are a chain, so everything after a
        # failure is cancelled rather than attempted against a half-built SDK.
        report = Runner(1).run(
            [
                Work(key=unit.unit, label=unit.unit, action=self._builder(unit))
                for unit in plan.units
            ],
            observer=observer,
        )
        return BuildReport(
            plan=plan,
            rows=report_rows(plan, report),
            interrupted=report.interrupted,
        )

    def perform(
        self,
        root: Path,
        branch_set: str,
        *,
        profile: Profile,
        names: Sequence[str] = (),
        downstream: str | None = None,
        passthrough: Sequence[str] = (),
        observer: RunObserver | None = None,
    ) -> BuildReport:
        return self.apply(
            self.plan(
                root,
                branch_set,
                profile=profile,
                names=names,
                downstream=downstream,
                passthrough=passthrough,
            ),
            observer=observer,
        )

    def _builder(self, unit: UnitPlan) -> Callable[[], float]:
        def build() -> float:
            began = time.monotonic()
            with self._lock(unit.lock):
                for link in unit.stale:
                    self._fs.remove(link)
                for move in unit.recover:
                    self._fs.move(move.source, move.destination)
                # Written before anything moves in, so that whatever is in the
                # worktree from here on is attributed to this profile.
                self._fs.write_text(unit.marker, unit.moved)
                for move in unit.scratch:
                    self._fs.move(move.source, move.destination)
                # Ctrl-C lands in the main thread, not here: the build gets the
                # signal too, and this waits for it to exit before moving
                # anything. Only a killed cjdev leaves scratch behind, and the
                # marker is how the next run finds it.
                try:
                    self._steps(unit)
                finally:
                    self._move_out(unit)
            return time.monotonic() - began

        return build

    def _steps(self, unit: UnitPlan) -> None:
        for step in unit.steps:
            if isinstance(step, Copy):
                self._fs.copy(step.source, step.into)
            else:
                self._executor.run(step)

    def _move_out(self, unit: UnitPlan) -> None:
        for move in reversed(unit.scratch):
            self._fs.move(move.destination, move.source)
        self._fs.remove(unit.marker)


def _unique(paths: Iterable[PurePath]) -> tuple[PurePath, ...]:
    return tuple(dict.fromkeys(paths))
