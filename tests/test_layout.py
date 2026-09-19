from pathlib import Path, PurePath, PurePosixPath

import pytest

from cjdev.domain.layout import (
    WorkspaceLayout,
    flatten_branch_set,
    relative_target,
)
from cjdev.errors import UsageError

ROOT = Path("/ws")
CJDEV = ROOT / ".cjdev"
COMPILER = "cangjie_compiler"
STDLIB = "stdlib"


@pytest.fixture
def layout() -> WorkspaceLayout:
    return WorkspaceLayout(ROOT)


class TestWorkspaceTree:
    """The documented tree: branch sets in the root, everything else hidden."""

    def test_branch_sets_are_the_only_thing_in_the_root(self, layout: WorkspaceLayout):
        # The root is the part a person browses and `cd`s into. Everything
        # else is the tool's, and hiding it is what keeps that true as
        # build/, dist/, log/ and cache/ accumulate.
        assert layout.branch_set_dir("fix/ice") == ROOT / "fix-ice"
        assert layout.worktree("fix/ice", COMPILER) == (
            ROOT / "fix-ice" / "cangjie_compiler"
        )

        internals = [
            layout.config_file,
            layout.bare_dir,
            layout.cache_dir,
            layout.log_dir("fix/ice"),
            layout.build_dir("fix/ice", "host", "debug", STDLIB),
            layout.dist_dir("fix/ice", "host", "debug"),
        ]
        assert all(CJDEV in path.parents for path in internals)

    def test_the_config_lives_inside_the_marker(self, layout: WorkspaceLayout):
        assert layout.config_file == CJDEV / "config.toml"

    def test_one_bare_object_store_per_project(self, layout: WorkspaceLayout):
        assert layout.object_store(COMPILER) == (
            CJDEV / "bare" / "cangjie_compiler.git"
        )

    def test_build_dirs_are_keyed_by_set_environment_profile_and_unit(
        self, layout: WorkspaceLayout
    ):
        assert layout.build_dir("fix/ice", "host", "debug", STDLIB) == (
            CJDEV / "build" / "fix-ice" / "host" / "debug" / "stdlib"
        )

    def test_dist_is_keyed_the_same_way(self, layout: WorkspaceLayout):
        # The two environments build different targets from different
        # toolchains, and one `bin/cjc` cannot be both.
        assert layout.dist_dir("main", "container", "release") == (
            CJDEV / "dist" / "main" / "container" / "release"
        )

    def test_logs_are_per_branch_set(self, layout: WorkspaceLayout):
        assert layout.log_dir("fix/ice") == CJDEV / "log" / "fix-ice"


class TestFlattening:
    def test_slashes_become_dashes(self):
        assert flatten_branch_set("fix/parser-ice-1234") == "fix-parser-ice-1234"

    def test_a_name_without_slashes_is_unchanged(self):
        assert flatten_branch_set("main") == "main"

    def test_the_directory_name_stays_one_segment(self, layout: WorkspaceLayout):
        # The whole point: no nesting appears in the root, however deep the
        # branch name is.
        assert layout.branch_set_dir("a/b/c").parent == ROOT

    def test_flattening_is_not_injective_and_that_is_documented(self):
        # Two different branches, one directory. Recorded as a test because it
        # is the reason the branch in git - not the directory - is the identity
        # of a branch set, and the reason `branch new` has to refuse a
        # colliding name rather than silently reuse a worktree.
        assert flatten_branch_set("fix/ice") == flatten_branch_set("fix-ice")


class TestCacheIsShared:
    def test_ccache_is_not_keyed_by_anything(self, layout: WorkspaceLayout):
        # One store for every branch set and every environment mode. A
        # parameter here would be the bug that quietly kills cross-branch
        # reuse, so the absence of one is the thing worth asserting.
        assert layout.ccache_dir == CJDEV / "cache" / "ccache"


class TestBranchSetNamesFollowGitsRules:
    """`git check-ref-format`'s rules, which also keep paths inside the root."""

    @pytest.mark.parametrize("name", ["../evil", "fix/../evil", ".", ".hidden"])
    def test_a_component_may_not_start_with_a_dot(
        self, layout: WorkspaceLayout, name: str
    ):
        with pytest.raises(UsageError, match="must not start with"):
            layout.branch_set_dir(name)

    @pytest.mark.parametrize("name", ["/etc", "fix/", "a//b"])
    def test_empty_or_edge_slashes_are_refused(
        self, layout: WorkspaceLayout, name: str
    ):
        with pytest.raises(UsageError):
            layout.branch_set_dir(name)

    def test_an_empty_name_is_refused(self, layout: WorkspaceLayout):
        with pytest.raises(UsageError, match="must not be empty"):
            layout.branch_set_dir("")

    def test_the_marker_cannot_be_shadowed(self, layout: WorkspaceLayout):
        # `.cjdev` is not a legal branch name anyway - git forbids a leading
        # dot - but the layout refuses it rather than relying on that.
        with pytest.raises(UsageError):
            layout.branch_set_dir(".cjdev")

    def test_a_profile_may_not_be_a_path(self, layout: WorkspaceLayout):
        # Branch-set names may nest in git; profiles are plain names.
        with pytest.raises(UsageError, match="single path segment"):
            layout.dist_dir("main", "host", "debug/x86")

    def test_a_build_unit_may_not_be_a_path_either(self, layout: WorkspaceLayout):
        # Unit names are the flat token `cjdev build <unit>` takes, so one
        # containing a slash is a manifest mistake rather than nesting.
        with pytest.raises(UsageError, match="single path segment"):
            layout.build_dir("main", "host", "debug", "cangjie_runtime/stdlib")


class TestBranchSetIsolation:
    def test_two_branch_sets_never_share_a_build_dir(self, layout: WorkspaceLayout):
        # This is what makes switching branch sets cheap.
        assert layout.build_dir("a", "host", "debug", STDLIB) != layout.build_dir(
            "b", "host", "debug", STDLIB
        )

    def test_two_profiles_never_share_a_build_dir(self, layout: WorkspaceLayout):
        assert layout.build_dir("a", "host", "debug", STDLIB) != layout.build_dir(
            "a", "host", "release", STDLIB
        )

    def test_a_layout_works_from_a_root_that_cannot_do_io(self):
        # `PurePath` has no exists/mkdir/read_text, so a layout built on one
        # cannot touch the filesystem even by accident. `ty` enforces this
        # statically; the test pins the runtime half.
        layout = WorkspaceLayout(PurePath("/nowhere"))

        assert layout.worktree("any", COMPILER).name == "cangjie_compiler"
        assert not hasattr(layout.marker, "mkdir")


class TestBuildPaths:
    def test_a_scratch_directory_keeps_its_shape_under_the_build_dir(
        self, layout: WorkspaceLayout
    ):
        # Arrange / Act
        real = layout.scratch_dir(
            "main", "host", "debug", "cjpm", PurePosixPath("cpp/out")
        )

        # Assert: nested rather than flattened, so `build/bin` and `build-bin`
        # cannot collide.
        assert real == (
            CJDEV / "build" / "main" / "host" / "debug" / "cjpm" / "cpp" / "out"
        )

    def test_the_build_lock_sits_above_the_profile(self, layout: WorkspaceLayout):
        # Act
        lock = layout.build_lock("fix/ice", "compiler")

        # Assert: the profile is what it guards, so it cannot be keyed by it.
        assert lock == CJDEV / "build" / "fix-ice" / "compiler.lock"

    def test_one_log_file_per_unit_under_the_branch_sets_directory(
        self, layout: WorkspaceLayout
    ):
        # Act / Assert
        assert layout.unit_log("fix/ice", STDLIB) == (
            CJDEV / "log" / "fix-ice" / "stdlib.log"
        )

    def test_stdx_installs_inside_the_shared_dist(self, layout: WorkspaceLayout):
        # Act / Assert: anything else would let removing build artefacts break
        # an already-installed SDK.
        assert layout.stdx_dir("main", "host", "release") == (
            layout.dist_dir("main", "host", "release") / "third_party" / "stdx"
        )
        assert layout.stdx_lib_dir("main", "host", "release", "linux_x86_64") == (
            layout.stdx_dir("main", "host", "release")
            / "linux_x86_64_cjnative"
            / "static"
            / "stdx"
        )

    def test_the_ccache_shim_is_keyed_by_environment(self, layout: WorkspaceLayout):
        # Act / Assert: the link names a ccache binary, and the two
        # environments have it in different places.
        assert layout.shim_dir("host") == layout.cache_dir / "shim" / "host"
        assert layout.shim_dir("container") != layout.shim_dir("host")

    def test_a_traversing_unit_name_cannot_reach_out_of_the_workspace(
        self, layout: WorkspaceLayout
    ):
        # Act / Assert: these paths are removed, so a name that escapes is the
        # whole risk.
        with pytest.raises(UsageError):
            layout.build_lock("main", "../../etc")
        with pytest.raises(UsageError):
            layout.unit_log("main", "..")


class TestRelativeTargets:
    def test_a_link_in_a_worktree_reaches_the_build_directory_by_dots(
        self, layout: WorkspaceLayout
    ):
        # Arrange
        link = layout.worktree("main", COMPILER) / "build"
        real = layout.build_dir("main", "host", "release", "compiler") / "build"

        # Act / Assert: relative, because an absolute target breaks the moment
        # the workspace is mounted somewhere else.
        assert relative_target(link, real) == PurePath(
            "../../.cjdev/build/main/host/release/compiler/build"
        )

    def test_a_deeper_link_needs_more_dots(self, layout: WorkspaceLayout):
        # Arrange
        link = layout.worktree("main", COMPILER) / "cjpm" / "cpp" / "out"
        real = layout.build_dir("main", "host", "release", "cjpm") / "cpp" / "out"

        # Act
        target = relative_target(link, real)

        # Assert
        assert target.parts[:4] == ("..", "..", "..", "..")


class TestSdkEnvironment:
    def test_path_carries_both_of_the_sdks_bin_directories(
        self, layout: WorkspaceLayout
    ):
        # Act / Assert: `bin` without `tools/bin` is a PATH that works until
        # the first `cjpm` invocation.
        dist = layout.dist_dir("main", "host", "release")

        assert layout.sdk_path("main", "host", "release") == (
            dist / "bin",
            dist / "tools" / "bin",
        )

    def test_the_library_path_is_keyed_by_the_runtime_target(
        self, layout: WorkspaceLayout
    ):
        # Act
        entries = layout.sdk_library_path("main", "host", "release", "linux_x86_64")

        # Assert
        dist = layout.dist_dir("main", "host", "release")
        assert entries == (
            dist / "runtime" / "lib" / "linux_x86_64_cjnative",
            dist / "tools" / "lib",
        )
