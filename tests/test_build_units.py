"""`cjdev build`: the decision, and then the same build against a real tree.

The decision is asserted with no filesystem in sight. The redirects are not:
they are built on what a symlink does to a script that derives its output
directory from `__file__`, which only a real tree can be trusted about.
"""

import os
import subprocess
import threading
from dataclasses import replace
from pathlib import Path, PurePath, PurePosixPath
from typing import final

import pytest

from cjdev.application.build_units import (
    EXCLUDE_HEADER,
    BuildPlan,
    BuildUnits,
    Copy,
    LinkState,
    Observed,
    Seen,
    decide,
    observe,
    select_units,
)
from cjdev.application.ports import Command, Completed
from cjdev.application.runner import Outcome
from cjdev.domain.build import CopyStep, Host, Profile, RunStep, native_target
from cjdev.domain.layout import WorkspaceLayout, relative_target
from cjdev.domain.manifest import BuildUnit, Manifest, Project, ProjectRole
from cjdev.errors import CommandError, PreconditionError, UsageError
from cjdev.infra.executor import build_executor
from cjdev.infra.executor.host import HostExecutor
from cjdev.infra.filesystem import HostFileSystem, build_file_system
from cjdev.infra.locks import file_lock, no_lock
from conftest import make_upstream

LAYOUT = WorkspaceLayout(PurePath("/ws"))
SET = "main"
HOST = Host(
    target="linux_x86_64",
    jobs=4,
    path="/usr/bin",
    library_var="LD_LIBRARY_PATH",
    library_path="/lib",
    ccache=None,
)
WITH_CCACHE = replace(HOST, ccache=PurePath("/usr/bin/ccache"))

BUILD_ARGV = ("python3", "build.py", "build", "-t", "{profile}", "-j", "{jobs}")
INSTALL_ARGV = ("python3", "build.py", "install", "--prefix", "{dist}")


def unit(
    name: str,
    *,
    project: str = "alpha",
    path: str = ".",
    depends_on: tuple[str, ...] = (),
    scratch: tuple[str, ...] = ("build", "output"),
    build: tuple[str, ...] = BUILD_ARGV,
    install: tuple[RunStep | CopyStep, ...] = (RunStep(INSTALL_ARGV),),
    extra_args: tuple[str, ...] = (),
) -> BuildUnit:
    return BuildUnit(
        name=name,
        project=project,
        path=PurePosixPath(path),
        depends_on=depends_on,
        scratch=tuple(PurePosixPath(s) for s in scratch),
        build=build,
        install=install,
        extra_args=extra_args,
    )


def manifest(
    *units: BuildUnit, projects: tuple[str, ...] = ("alpha", "beta")
) -> Manifest:
    return Manifest(
        schema_version=2,
        projects=tuple(
            Project(
                name=name,
                role=ProjectRole.BUILDABLE,
                upstream_url=f"file:///upstreams/{name}",
                default_branch="main",
            )
            for name in projects
        ),
        build_units=units,
    )


def seen(
    scratch: str, state: LinkState = LinkState.ABSENT, target: str | None = None
) -> Seen:
    return Seen(
        scratch=PurePosixPath(scratch),
        state=state,
        target=None if target is None else PurePosixPath(target),
    )


def observed(
    *units: BuildUnit,
    links: dict[str, tuple[Seen, ...]] | None = None,
    excludes: dict[str, str] | None = None,
    worktrees: frozenset[str] | None = None,
) -> Observed:
    return Observed(
        links=links
        if links is not None
        else {u.name: tuple(seen(str(s)) for s in u.scratch) for u in units},
        excludes=excludes or {},
        worktrees=worktrees
        if worktrees is not None
        else frozenset(u.project for u in units),
    )


def plan_of(
    *units: BuildUnit,
    profile: Profile = Profile.RELEASE,
    host: Host = HOST,
    passthrough: tuple[str, ...] = (),
    state: Observed | None = None,
) -> BuildPlan:
    return decide(
        LAYOUT,
        SET,
        profile,
        units,
        host,
        state if state is not None else observed(*units),
        passthrough=passthrough,
    )


class TestSelection:
    def test_naming_a_unit_takes_what_it_depends_on_with_it(self):
        # Arrange
        graph = manifest(unit("compiler"), unit("stdlib", depends_on=("compiler",)))

        # Act
        selected = select_units(graph, ["stdlib"])

        # Assert
        assert [u.name for u in selected] == ["compiler", "stdlib"]

    def test_naming_a_project_takes_every_unit_it_holds(self):
        # Arrange
        graph = manifest(
            unit("runtime", project="beta"), unit("stdlib", project="beta")
        )

        # Act
        selected = select_units(graph, ["beta"])

        # Assert
        assert [u.name for u in selected] == ["runtime", "stdlib"]

    def test_no_selection_is_the_whole_graph(self):
        # Arrange
        graph = manifest(unit("compiler"), unit("stdlib", depends_on=("compiler",)))

        # Act
        selected = select_units(graph, [])

        # Assert
        assert [u.name for u in selected] == ["compiler", "stdlib"]

    def test_from_takes_everything_downstream(self):
        # Arrange
        graph = manifest(unit("compiler"), unit("stdlib", depends_on=("compiler",)))

        # Act
        selected = select_units(graph, [], downstream="compiler")

        # Assert
        assert [u.name for u in selected] == ["compiler", "stdlib"]

    def test_from_and_a_named_unit_together_are_refused(self):
        # Arrange
        graph = manifest(unit("compiler"))

        # Act / Assert: the result would depend on which was applied first.
        with pytest.raises(UsageError, match="one or the other"):
            select_units(graph, ["compiler"], downstream="compiler")

    def test_an_unknown_name_lists_both_vocabularies(self):
        # Arrange
        graph = manifest(unit("compiler"))

        # Act / Assert
        with pytest.raises(UsageError, match=r"Units: compiler.*Projects: alpha"):
            select_units(graph, ["complier"])

    def test_a_project_with_no_units_says_so(self):
        # Arrange
        graph = manifest(unit("compiler"))

        # Act / Assert
        with pytest.raises(UsageError, match="holds no build units"):
            select_units(graph, ["beta"])


class TestRedirects:
    def test_a_scratch_path_points_out_of_the_worktree_relatively(self):
        # Act
        plan = plan_of(unit("compiler"))

        # Assert
        build = plan.units[0].redirects[0]
        assert build.link == PurePath("/ws/main/alpha/build")
        assert build.real == PurePath("/ws/.cjdev/build/main/release/compiler/build")
        assert build.target == PurePosixPath(
            "../../.cjdev/build/main/release/compiler/build"
        )

    def test_a_nested_scratch_path_keeps_its_shape_on_both_sides(self):
        # Arrange
        cjpm = unit("cjpm", path="cjpm", scratch=("cpp/out",))

        # Act
        plan = plan_of(cjpm)

        # Assert
        redirect = plan.units[0].redirects[0]
        assert redirect.link == PurePath("/ws/main/alpha/cjpm/cpp/out")
        assert redirect.real == PurePath("/ws/.cjdev/build/main/release/cjpm/cpp/out")

    def test_a_link_already_on_this_profile_is_left_alone(self):
        # Arrange
        target = "../../.cjdev/build/main/release/compiler/build"
        compiler = unit("compiler", scratch=("build",))

        # Act
        plan = plan_of(
            compiler,
            state=observed(
                compiler, links={"compiler": (seen("build", LinkState.LINKED, target),)}
            ),
        )

        # Assert
        assert plan.units[0].redirects[0].linked

    def test_a_link_on_another_profile_is_repointed(self):
        # Arrange
        compiler = unit("compiler", scratch=("build",))
        debug = "../../.cjdev/build/main/debug/compiler/build"

        # Act
        plan = plan_of(
            compiler,
            state=observed(
                compiler, links={"compiler": (seen("build", LinkState.LINKED, debug),)}
            ),
        )

        # Assert
        assert not plan.units[0].redirects[0].linked

    def test_a_real_directory_where_the_link_belongs_is_refused(self):
        # Arrange: somebody built here by hand, and their artefacts are theirs.
        compiler = unit("compiler", scratch=("build",))

        # Act / Assert
        with pytest.raises(PreconditionError, match="real directory") as refused:
            plan_of(
                compiler,
                state=observed(
                    compiler,
                    links={"compiler": (seen("build", LinkState.OCCUPIED),)},
                ),
            )
        assert refused.value.remedy == "move or delete /ws/main/alpha/build"

    def test_a_missing_worktree_names_the_command_that_makes_one(self):
        # Arrange
        compiler = unit("compiler")

        # Act / Assert
        with pytest.raises(PreconditionError) as refused:
            plan_of(compiler, state=observed(compiler, worktrees=frozenset()))
        assert refused.value.remedy == f"cjdev branch new {SET}"


class TestSteps:
    def test_the_tokens_are_substituted_in_build_and_install(self):
        # Act
        plan = plan_of(unit("compiler"))

        # Assert
        build, install = plan.units[0].steps
        assert isinstance(build, Command) and isinstance(install, Command)
        assert build.argv == (
            "python3",
            "build.py",
            "build",
            "-t",
            "release",
            "-j",
            "4",
        )
        assert install.argv[-1] == "/ws/.cjdev/dist/main/release"

    def test_extra_args_then_passthrough_follow_the_template(self):
        # Arrange
        compiler = unit("compiler", extra_args=("--no-tests",))

        # Act
        plan = plan_of(compiler, passthrough=("--hwasan",))

        # Assert
        build = plan.units[0].steps[0]
        assert isinstance(build, Command)
        assert build.argv[-2:] == ("--no-tests", "--hwasan")

    def test_passthrough_needs_the_selection_to_be_one_unit(self):
        # Arrange: there is no honest answer to which script a raw flag meant.
        units = (unit("compiler"), unit("stdlib", depends_on=("compiler",)))

        # Act / Assert
        with pytest.raises(UsageError, match="resolves to 2 units"):
            plan_of(*units, passthrough=("--hwasan",))

    def test_a_copy_install_step_resolves_both_ends(self):
        # Arrange
        cjpm = unit(
            "cjpm",
            path="cjpm",
            install=(CopyStep(PurePosixPath("dist/cjpm"), "{dist}/tools/bin"),),
        )

        # Act
        plan = plan_of(cjpm)

        # Assert
        copy = plan.units[0].steps[1]
        assert copy == Copy(
            source=PurePath("/ws/main/alpha/cjpm/dist/cjpm"),
            into=PurePath("/ws/.cjdev/dist/main/release/tools/bin"),
        )

    def test_every_command_writes_to_the_units_own_log(self):
        # Act
        plan = plan_of(unit("compiler"))

        # Assert
        assert all(
            step.log == PurePath("/ws/.cjdev/log/main/compiler.log")
            for step in plan.units[0].steps
            if isinstance(step, Command)
        )

    def test_a_unit_with_no_build_command_is_refused_rather_than_guessed_at(self):
        # Arrange
        interop = unit("interop", build=(), install=())

        # Act / Assert
        with pytest.raises(PreconditionError, match="no build command"):
            plan_of(interop)


class TestEnvironment:
    def test_the_sdk_under_construction_travels_in_the_environment(self):
        # Act
        plan = plan_of(unit("compiler"))

        # Assert
        build = plan.units[0].steps[0]
        assert isinstance(build, Command)
        assert build.env["CANGJIE_HOME"] == "/ws/.cjdev/dist/main/release"
        assert build.env["CANGJIE_STDX_PATH"] == (
            "/ws/.cjdev/dist/main/release/third_party/stdx/"
            "linux_x86_64_cjnative/static/stdx"
        )

    def test_the_sdk_is_on_path_so_the_next_unit_can_find_cjc(self):
        # Arrange: stdlib, stdx and cjpm all invoke `cjc` by name, which is
        # what `source envsetup.sh` would otherwise arrange.
        # Act
        plan = plan_of(unit("compiler"))

        # Assert
        build = plan.units[0].steps[0]
        assert isinstance(build, Command)
        assert build.env["PATH"].split(os.pathsep) == [
            "/ws/.cjdev/dist/main/release/bin",
            "/ws/.cjdev/dist/main/release/tools/bin",
            "/usr/bin",
        ]
        assert build.env["LD_LIBRARY_PATH"].split(os.pathsep) == [
            "/ws/.cjdev/dist/main/release/runtime/lib/linux_x86_64_cjnative",
            "/ws/.cjdev/dist/main/release/tools/lib",
            "/lib",
        ]

    def test_an_empty_inherited_path_leaves_no_trailing_separator(self):
        # Arrange: an empty entry is the current directory to a shell.
        # Act
        plan = plan_of(unit("compiler"), host=replace(HOST, path="", library_path=""))

        # Assert
        build = plan.units[0].steps[0]
        assert isinstance(build, Command)
        assert not build.env["PATH"].endswith(os.pathsep)
        assert not build.env["LD_LIBRARY_PATH"].endswith(os.pathsep)

    def test_without_ccache_there_is_no_shim(self):
        # Act
        plan = plan_of(unit("compiler"))

        # Assert
        build = plan.units[0].steps[0]
        assert isinstance(build, Command)
        assert plan.shims == ()
        assert "CCACHE_DIR" not in build.env

    def test_ccache_arrives_as_a_shim_on_path_and_a_shared_store(self):
        # Arrange: `stdlib/build.py` overwrites CC and CXX from its own
        # `shutil.which`, so only something on PATH survives.
        # Act
        plan = plan_of(unit("compiler"), host=WITH_CCACHE)

        # Assert
        build = plan.units[0].steps[0]
        assert isinstance(build, Command)
        # In front of the SDK's own directories: the shim stands in for the C
        # compiler, which the SDK does not provide.
        assert build.env["PATH"].split(os.pathsep)[0] == "/ws/.cjdev/cache/shim"
        assert build.env["CCACHE_DIR"] == "/ws/.cjdev/cache/ccache"
        # BASEDIR is what makes one store serve every branch set.
        assert build.env["CCACHE_BASEDIR"] == "/ws"
        assert [str(shim.link) for shim in plan.shims] == [
            "/ws/.cjdev/cache/shim/clang",
            "/ws/.cjdev/cache/shim/clang++",
        ]


class TestExclusions:
    def test_scratch_paths_are_written_into_the_stores_own_exclude(self):
        # Arrange: cjpm's scratch paths are not gitignored, so the symlinks
        # would otherwise make every worktree of the project dirty.
        cjpm = unit("cjpm", path="cjpm", scratch=("dist", "cpp/out"))

        # Act
        plan = plan_of(cjpm)

        # Assert
        exclusion = plan.exclusions[0]
        assert exclusion.path == PurePath("/ws/.cjdev/bare/alpha.git/info/exclude")
        assert exclusion.text.splitlines() == [
            EXCLUDE_HEADER,
            "/cjpm/dist",
            "/cjpm/cpp/out",
        ]

    def test_what_the_file_already_says_is_kept_and_not_repeated(self):
        # Arrange
        compiler = unit("compiler", scratch=("build", "output"))

        # Act
        plan = plan_of(
            compiler,
            state=observed(compiler, excludes={"alpha": "*.swp\n/build\n"}),
        )

        # Assert
        assert plan.exclusions[0].text.splitlines() == [
            "*.swp",
            "/build",
            EXCLUDE_HEADER,
            "/output",
        ]

    def test_a_store_that_already_lists_everything_is_left_alone(self):
        # Arrange
        compiler = unit("compiler", scratch=("build",))

        # Act
        plan = plan_of(
            compiler, state=observed(compiler, excludes={"alpha": "/build\n"})
        )

        # Assert
        assert plan.exclusions == ()

    def test_two_units_of_one_project_produce_one_write(self):
        # Arrange: two writes each computed from the same original text would
        # lose the first one's lines.
        units = (
            unit("runtime", path="runtime", scratch=("output",)),
            unit("stdlib", path="stdlib", scratch=("output",)),
        )

        # Act
        plan = plan_of(*units)

        # Assert
        assert len(plan.exclusions) == 1
        assert plan.exclusions[0].text.splitlines()[1:] == [
            "/runtime/output",
            "/stdlib/output",
        ]


@final
class FakeExecutor:
    """Records what ran, and fails whatever it is told to."""

    def __init__(self, failing: str | None = None) -> None:
        self.ran: list[tuple[str, ...]] = []
        self._failing = failing

    def run(self, command: Command, *, check: bool = True) -> Completed:
        self.ran.append(command.argv)
        if self._failing is not None and self._failing in command.argv:
            raise CommandError(command.argv, str(command.cwd), 1, "boom")
        return Completed(command, 0, "", "")


@final
class FakeFileSystem:
    def __init__(self) -> None:
        self.made: list[PurePath] = []
        self.links: list[tuple[PurePath, PurePath]] = []
        self.copied: list[tuple[PurePath, PurePath]] = []
        self.written: list[PurePath] = []

    def mkdir(self, path: PurePath) -> None:
        self.made.append(path)

    def write_text(self, path: PurePath, text: str) -> None:
        del text
        self.written.append(path)

    def remove(self, path: PurePath) -> None:
        del path

    def symlink(self, link: PurePath, target: PurePath) -> None:
        self.links.append((link, target))

    def copy(self, source: PurePath, into: PurePath) -> None:
        self.copied.append((source, into))


def use_case(
    graph: Manifest, executor: FakeExecutor, fs: FakeFileSystem, host: Host = HOST
) -> BuildUnits:
    return BuildUnits(
        manifest=lambda: graph,
        executor=executor,  # type: ignore[arg-type]
        file_system=fs,  # type: ignore[arg-type]
        host=host,
        lock=no_lock,
    )


class TestApply:
    def test_the_chain_runs_in_dependency_order_one_unit_at_a_time(self):
        # Arrange
        units = (unit("compiler"), unit("stdlib", depends_on=("compiler",)))
        executor, fs = FakeExecutor(), FakeFileSystem()

        # Act
        report = use_case(manifest(*units), executor, fs).apply(plan_of(*units))

        # Assert
        assert report.ok
        assert [row.unit for row in report.rows] == ["compiler", "stdlib"]
        assert len(executor.ran) == 4

    def test_a_failure_cancels_everything_after_it(self):
        # Arrange: the units are a chain, so the rest would build against a
        # half-built SDK.
        units = (unit("compiler"), unit("stdlib", depends_on=("compiler",)))
        executor, fs = FakeExecutor(failing="build"), FakeFileSystem()

        # Act
        report = use_case(manifest(*units), executor, fs).apply(plan_of(*units))

        # Assert
        assert not report.ok
        assert [row.outcome for row in report.rows] == [
            Outcome.FAILED,
            Outcome.CANCELLED,
        ]

    def test_only_the_links_that_are_wrong_are_rewritten(self):
        # Arrange
        compiler = unit("compiler", scratch=("build", "output"))
        state = observed(
            compiler,
            links={
                "compiler": (
                    seen(
                        "build",
                        LinkState.LINKED,
                        "../../.cjdev/build/main/release/compiler/build",
                    ),
                    seen("output"),
                )
            },
        )
        executor, fs = FakeExecutor(), FakeFileSystem()

        # Act
        use_case(manifest(compiler), executor, fs).apply(plan_of(compiler, state=state))

        # Assert
        assert [str(link) for link, _ in fs.links] == ["/ws/main/alpha/output"]

    def test_a_copy_install_goes_through_the_port(self):
        # Arrange: a `cp` in the manifest would route a tree mutation around
        # --dry-run.
        cjpm = unit(
            "cjpm",
            install=(CopyStep(PurePosixPath("dist/cjpm"), "{dist}/tools/bin"),),
        )
        executor, fs = FakeExecutor(), FakeFileSystem()

        # Act
        use_case(manifest(cjpm), executor, fs).apply(plan_of(cjpm))

        # Assert
        assert fs.copied == [
            (
                PurePath("/ws/main/alpha/dist/cjpm"),
                PurePath("/ws/.cjdev/dist/main/release/tools/bin"),
            )
        ]


SCRIPT = """\
import os, sys
here = os.path.dirname(os.path.abspath(__file__))
step = sys.argv[1]
os.makedirs(os.path.join(here, "build"), exist_ok=True)
os.makedirs(os.path.join(here, "output"), exist_ok=True)
open(os.path.join(here, "output", step), "w").write(step)
print("ran", step, flush=True)
"""
"""A stand-in for an upstream `build.py`: it derives its output directory from
`__file__`, which is the whole reason the redirect is a symlink."""


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    worktree = root / SET / "alpha"
    worktree.mkdir(parents=True)
    (worktree / "build.py").write_text(SCRIPT, encoding="utf-8")
    Path(WorkspaceLayout(root).object_store("alpha") / "info").mkdir(parents=True)
    return root


def real_build(root: Path, graph: Manifest, **overrides: object) -> BuildUnits:
    wiring: dict[str, object] = {
        "manifest": lambda: graph,
        "executor": HostExecutor(),
        "file_system": HostFileSystem(),
        "host": replace(HOST, path=os.environ.get("PATH", "")),
        "lock": file_lock,
    }
    wiring.update(overrides)
    del root
    return BuildUnits(**wiring)  # type: ignore[arg-type]


REAL = unit(
    "compiler",
    build=("python3", "build.py", "build"),
    install=(RunStep(("python3", "build.py", "install")),),
)


class TestAgainstARealTree:
    def test_the_artefacts_land_outside_the_worktree(self, workspace: Path):
        # Arrange
        layout = WorkspaceLayout(workspace)

        # Act
        report = real_build(workspace, manifest(REAL)).perform(
            workspace, SET, profile=Profile.RELEASE
        )

        # Assert
        assert report.ok, report.rows[0].error
        real = Path(
            layout.scratch_dir(SET, "release", "compiler", PurePosixPath("output"))
        )
        assert sorted(p.name for p in real.iterdir()) == ["build", "install"]
        assert Path(workspace / SET / "alpha" / "output").is_symlink()

    def test_the_symlink_is_relative_so_the_tree_can_be_mounted_elsewhere(
        self, workspace: Path
    ):
        # Act
        real_build(workspace, manifest(REAL)).perform(
            workspace, SET, profile=Profile.RELEASE
        )

        # Assert
        link = workspace / SET / "alpha" / "build"
        assert not link.readlink().is_absolute()

    def test_switching_profile_repoints_and_keeps_the_other_profiles_work(
        self, workspace: Path
    ):
        # Arrange
        build = real_build(workspace, manifest(REAL))
        build.perform(workspace, SET, profile=Profile.RELEASE)

        # Act
        build.perform(workspace, SET, profile=Profile.DEBUG)

        # Assert
        layout = WorkspaceLayout(workspace)
        for profile in ("release", "debug"):
            kept = Path(
                layout.scratch_dir(SET, profile, "compiler", PurePosixPath("output"))
            )
            assert (kept / "build").is_file()
        assert (workspace / SET / "alpha" / "build").readlink() == Path(
            relative_target(
                layout.worktree(SET, "alpha") / "build",
                layout.build_dir(SET, "debug", "compiler") / "build",
            )
        )

    def test_the_output_is_teed_into_the_units_log_while_it_runs(self, workspace: Path):
        # Act
        real_build(workspace, manifest(REAL)).perform(
            workspace, SET, profile=Profile.RELEASE
        )

        # Assert
        log = Path(WorkspaceLayout(workspace).unit_log(SET, "compiler"))
        assert log.read_text(encoding="utf-8").splitlines() == [
            "ran build",
            "ran install",
        ]

    def test_the_scratch_paths_reach_the_stores_exclude_file(self, workspace: Path):
        # Act
        real_build(workspace, manifest(REAL)).perform(
            workspace, SET, profile=Profile.RELEASE
        )

        # Assert
        exclude = Path(
            WorkspaceLayout(workspace).object_store("alpha") / "info" / "exclude"
        )
        assert "/build" in exclude.read_text(encoding="utf-8").splitlines()

    def test_a_worktree_directory_where_a_link_belongs_stops_the_build(
        self, workspace: Path
    ):
        # Arrange
        (workspace / SET / "alpha" / "build").mkdir()

        # Act / Assert
        with pytest.raises(PreconditionError, match="real directory"):
            real_build(workspace, manifest(REAL)).perform(
                workspace, SET, profile=Profile.RELEASE
            )

    def test_a_second_build_of_one_unit_refuses_rather_than_waits(
        self, workspace: Path
    ):
        # Arrange: blocking for forty minutes looks exactly like a hang.
        layout = WorkspaceLayout(workspace)
        lock = Path(layout.build_lock(SET, "compiler"))
        lock.parent.mkdir(parents=True, exist_ok=True)

        # Act
        with file_lock(lock):
            report = real_build(workspace, manifest(REAL)).perform(
                workspace, SET, profile=Profile.RELEASE
            )

        # Assert
        assert not report.ok
        assert isinstance(report.rows[0].error, PreconditionError)

    def test_a_dry_run_leaves_the_tree_exactly_as_it_was(self, workspace: Path):
        # Arrange
        printed: list[str] = []
        before = sorted(p.name for p in (workspace / SET / "alpha").iterdir())

        # Act
        real_build(
            workspace,
            manifest(REAL),
            executor=build_executor(dry_run=True, emit=printed.append),
            file_system=build_file_system(dry_run=True, emit=printed.append),
            lock=no_lock,
        ).perform(workspace, SET, profile=Profile.RELEASE)

        # Assert
        assert sorted(p.name for p in (workspace / SET / "alpha").iterdir()) == before
        assert not Path(WorkspaceLayout(workspace).marker / "build").exists()
        assert any(line.startswith("ln -sfn") for line in printed)
        assert any("build.py build" in line for line in printed)


class TestObserve:
    def test_it_reads_the_link_state_off_the_disk(self, workspace: Path):
        # Arrange
        link = workspace / SET / "alpha" / "build"
        link.symlink_to(PurePosixPath("../../.cjdev/build/main/debug/compiler/build"))
        (workspace / SET / "alpha" / "output").mkdir()

        # Act
        state = observe(WorkspaceLayout(workspace), SET, (unit("compiler"),))

        # Assert
        assert [s.state for s in state.links["compiler"]] == [
            LinkState.LINKED,
            LinkState.OCCUPIED,
        ]
        assert state.worktrees == frozenset({"alpha"})


def test_one_build_per_unit_and_set_is_what_the_lock_guards(tmp_path: Path):
    # Arrange: two runs of one unit would otherwise repoint each other's
    # scratch symlinks mid-build.
    layout = WorkspaceLayout(tmp_path)
    held = threading.Event()
    refused: list[Exception] = []

    def second() -> None:
        try:
            with file_lock(layout.build_lock(SET, "compiler")):
                pass
        except Exception as exc:
            refused.append(exc)

    # Act
    with file_lock(layout.build_lock(SET, "compiler")):
        held.set()
        worker = threading.Thread(target=second)
        worker.start()
        worker.join()

    # Assert
    assert len(refused) == 1
    # A different unit does not contend.
    with (
        file_lock(layout.build_lock(SET, "compiler")),
        file_lock(layout.build_lock(SET, "stdlib")),
    ):
        pass


def test_a_bare_repository_is_not_needed_to_decide_anything():
    # Arrange / Act
    state = observe(LAYOUT, SET, (unit("compiler"),))

    # Assert: a decision has to be assertable with nothing on disk.
    assert state.excludes == {"alpha": ""}
    assert state.worktrees == frozenset()


def test_subprocess_is_never_reached_by_a_plan(monkeypatch: pytest.MonkeyPatch):
    # Arrange
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("planning must not run anything")

    monkeypatch.setattr(subprocess, "run", forbidden)

    # Act
    plan = plan_of(unit("compiler"))

    # Assert
    assert plan.units


def test_a_passthrough_is_not_read_for_tokens():
    # Arrange: what follows `--` is the caller's, braces and all.
    compiler = unit("compiler")

    # Act
    plan = plan_of(compiler, passthrough=("--define", "X={unset}"))

    # Assert
    build = plan.units[0].steps[0]
    assert isinstance(build, Command)
    assert build.argv[-2:] == ("--define", "X={unset}")


def test_the_target_segment_canonicalises_the_arch_the_way_upstream_does():
    # Arrange / Act / Assert: envsetup.sh rewrites arm64, and every native
    # cmake toolchain file pins CMAKE_SYSTEM_PROCESSOR rather than taking the
    # host's word for it, so one spelling serves both.
    assert native_target("Linux", "x86_64") == "linux_x86_64"
    assert native_target("Linux", "aarch64") == "linux_aarch64"
    assert native_target("Darwin", "arm64") == "darwin_aarch64"
    assert native_target("Windows", "AMD64") == "windows_x86_64"


@pytest.mark.usefixtures("git_available")
class TestAgainstRealGit:
    """The ignore half, which only the real binary can be trusted about."""

    @pytest.fixture
    def enrolled(self, tmp_path: Path) -> Path:
        # Arrange: an upstream whose .gitignore writes the scratch path the way
        # `cangjie_runtime/runtime` and `cangjie_stdx` write theirs - with a
        # trailing slash - and a real linked worktree of it.
        upstream = tmp_path / "upstreams" / "alpha"
        make_upstream(upstream)
        (upstream / ".gitignore").write_text("output/\n", encoding="utf-8")
        (upstream / "build.py").write_text("print('ran')\n", encoding="utf-8")
        _git(upstream, "add", "-A")
        _git(upstream, "commit", "--quiet", "-m", "ignore")

        root = tmp_path / "ws"
        layout = WorkspaceLayout(root)
        store = Path(layout.object_store("alpha"))
        _run("git", "init", "--quiet", "--bare", str(store))
        _git(store, "remote", "add", "upstream", f"file://{upstream}")
        _git(store, "fetch", "--quiet", "upstream")
        worktree = Path(layout.worktree(SET, "alpha"))
        worktree.parent.mkdir(parents=True, exist_ok=True)
        _git(
            store,
            "worktree",
            "add",
            "--quiet",
            str(worktree),
            "refs/remotes/upstream/main",
        )
        return root

    def test_a_trailing_slash_pattern_does_not_cover_the_symlink(self, enrolled: Path):
        # Arrange
        worktree = Path(WorkspaceLayout(enrolled).worktree(SET, "alpha"))

        # Act
        (worktree / "output").symlink_to(PurePosixPath("../../.cjdev/build/x"))

        # Assert: a symlink is not a directory to git, which is why the build
        # cannot rely on the project's own ignore file.
        assert _status(worktree) == ["?? output"]

    def test_the_build_leaves_the_worktree_clean(self, enrolled: Path):
        # Arrange
        alpha = unit(
            "alpha",
            scratch=("output",),
            build=("python3", "build.py"),
            install=(),
        )

        # Act
        report = real_build(enrolled, manifest(alpha)).perform(
            enrolled, SET, profile=Profile.RELEASE
        )

        # Assert
        assert report.ok, report.rows[0].error
        worktree = Path(WorkspaceLayout(enrolled).worktree(SET, "alpha"))
        assert (worktree / "output").is_symlink()
        assert _status(worktree) == []

    def test_the_exclude_is_shared_by_every_branch_set_of_the_store(
        self, enrolled: Path
    ):
        # Arrange
        layout = WorkspaceLayout(enrolled)
        alpha = unit(
            "alpha", scratch=("output",), build=("python3", "build.py"), install=()
        )
        real_build(enrolled, manifest(alpha)).perform(
            enrolled, SET, profile=Profile.RELEASE
        )
        other = Path(layout.worktree("fix/ice", "alpha"))
        other.parent.mkdir(parents=True, exist_ok=True)

        # Act: a second branch set, enrolled after the first build wrote the
        # exclude.
        _git(
            Path(layout.object_store("alpha")),
            "worktree",
            "add",
            "--quiet",
            str(other),
            "refs/remotes/upstream/main",
        )
        (other / "output").symlink_to(PurePosixPath("../../.cjdev/build/y"))

        # Assert: one write covered it, because `info/exclude` belongs to the
        # store rather than to a worktree.
        assert _status(other) == []


def _run(*argv: str) -> str:
    return subprocess.run(list(argv), capture_output=True, text=True, check=True).stdout


def _git(cwd: Path, *argv: str) -> str:
    return subprocess.run(
        ["git", *argv], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _status(worktree: Path) -> list[str]:
    return _git(worktree, "status", "--porcelain").splitlines()


def test_a_mistyped_from_is_the_invocation_being_wrong():
    # Arrange: the same typo made positionally is a usage error, and one
    # mistake must not arrive as two failure classes.
    graph = manifest(unit("compiler"))

    # Act / Assert
    with pytest.raises(UsageError, match="unknown build unit complier"):
        select_units(graph, [], downstream="complier")


def test_the_exclude_header_is_written_once_however_often_the_set_grows():
    # Arrange: a store that already carries our marker and one of the lines.
    compiler = unit("compiler", scratch=("build", "output"))
    already = f"{EXCLUDE_HEADER}\n/build\n"

    # Act
    plan = plan_of(compiler, state=observed(compiler, excludes={"alpha": already}))

    # Assert
    text = plan.exclusions[0].text
    assert text.splitlines().count(EXCLUDE_HEADER) == 1
    assert text.splitlines()[-1] == "/output"
