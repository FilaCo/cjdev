from pathlib import Path, PurePath

import pytest

from cjdev.domain.layout import WorkspaceLayout, flatten_branch_set
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
            layout.build_dir("fix/ice", "debug", STDLIB),
            layout.dist_dir("fix/ice", "debug"),
        ]
        assert all(CJDEV in path.parents for path in internals)

    def test_the_config_lives_inside_the_marker(self, layout: WorkspaceLayout):
        assert layout.config_file == CJDEV / "config.toml"

    def test_one_bare_object_store_per_project(self, layout: WorkspaceLayout):
        assert layout.object_store(COMPILER) == (
            CJDEV / "bare" / "cangjie_compiler.git"
        )

    def test_build_dirs_are_keyed_by_branch_set_profile_and_unit(
        self, layout: WorkspaceLayout
    ):
        assert layout.build_dir("fix/ice", "debug", STDLIB) == (
            CJDEV / "build" / "fix-ice" / "debug" / "stdlib"
        )

    def test_dist_is_keyed_by_branch_set_and_profile(self, layout: WorkspaceLayout):
        assert layout.dist_dir("main", "release") == (
            CJDEV / "dist" / "main" / "release"
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
            layout.dist_dir("main", "debug/x86")

    def test_a_build_unit_may_not_be_a_path_either(self, layout: WorkspaceLayout):
        # Unit names are the flat token `cjdev build <unit>` takes, so one
        # containing a slash is a manifest mistake rather than nesting.
        with pytest.raises(UsageError, match="single path segment"):
            layout.build_dir("main", "debug", "cangjie_runtime/stdlib")


class TestBranchSetIsolation:
    def test_two_branch_sets_never_share_a_build_dir(self, layout: WorkspaceLayout):
        # This is what makes switching branch sets cheap.
        assert layout.build_dir("a", "debug", STDLIB) != layout.build_dir(
            "b", "debug", STDLIB
        )

    def test_two_profiles_never_share_a_build_dir(self, layout: WorkspaceLayout):
        assert layout.build_dir("a", "debug", STDLIB) != layout.build_dir(
            "a", "release", STDLIB
        )

    def test_a_layout_works_from_a_root_that_cannot_do_io(self):
        # `PurePath` has no exists/mkdir/read_text, so a layout built on one
        # cannot touch the filesystem even by accident. `ty` enforces this
        # statically; the test pins the runtime half.
        layout = WorkspaceLayout(PurePath("/nowhere"))

        assert layout.worktree("any", COMPILER).name == "cangjie_compiler"
        assert not hasattr(layout.marker, "mkdir")
