"""The branch set remembers the profile of its last full build.

The failure this exists for: an SDK built in debug, `cjdev build compiler`
defaulting to release, and a release dist holding a fresh `cjc` and no std
`.cjo` - every test after it would have failed on `import std.*`.
"""

from pathlib import Path, PurePath, PurePosixPath

import pytest

from cjdev.application.branch_set_profile import (
    BranchSetProfile,
    check_profile,
    unbuilt,
)
from cjdev.application.build_units import BuildUnits
from cjdev.domain.build import Host, Profile
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import BuildUnit, Manifest, Project, ProjectRole
from cjdev.domain.record import BranchSetRecord
from cjdev.errors import PreconditionError
from cjdev.infra.executor.host import HostExecutor
from cjdev.infra.filesystem import HostFileSystem
from cjdev.infra.locks import no_lock
from cjdev.infra.record import read_record, render_record

UNITS = ("compiler", "runtime", "stdlib")

MANIFEST = Manifest(
    schema_version=2,
    projects=(
        Project("cangjie_compiler", ProjectRole.BUILDABLE, "u", "main"),
        Project("cangjie_runtime", ProjectRole.BUILDABLE, "u", "main"),
    ),
    build_units=(
        BuildUnit("compiler", "cangjie_compiler", PurePosixPath("."), (), build=("b",)),
        BuildUnit(
            "runtime", "cangjie_runtime", PurePosixPath("runtime"), (), build=("b",)
        ),
        BuildUnit(
            "stdlib",
            "cangjie_runtime",
            PurePosixPath("stdlib"),
            ("compiler", "runtime"),
            build=("b",),
        ),
    ),
)

HOST = Host(
    target="linux_x86_64",
    jobs=1,
    path="",
    library_var="LD_LIBRARY_PATH",
    library_path="",
    ccache=None,
)


class TestUnbuilt:
    def test_every_unit_outside_the_selection_counts_not_only_dependencies(self):
        # Act: nothing in the graph says the compiler needs stdlib, but a dist
        # with a compiler and no stdlib compiles nothing.
        missing = unbuilt(["compiler"], UNITS, frozenset())

        # Assert
        assert missing == ("runtime", "stdlib")

    def test_what_the_profile_already_built_is_not_missing(self):
        # Act / Assert
        assert unbuilt(["compiler"], UNITS, frozenset({"runtime", "stdlib"})) == ()


class TestCheckProfile:
    def test_a_partial_build_in_another_profile_names_what_it_lacks(self):
        # Act / Assert
        with pytest.raises(PreconditionError) as refusal:
            check_profile(
                Profile.RELEASE,
                Profile.DEBUG,
                ("runtime", "stdlib"),
                branch_set="main",
            )
        assert "runtime, stdlib" in str(refusal.value)
        assert refusal.value.remedy == "cjdev build -p release"

    def test_the_branch_set_s_own_profile_is_never_refused(self):
        # Act / Assert
        check_profile(Profile.DEBUG, Profile.DEBUG, ("runtime",), branch_set="main")

    def test_a_branch_set_with_no_full_build_yet_has_nothing_to_disagree_with(self):
        # Act / Assert
        check_profile(Profile.RELEASE, None, ("runtime",), branch_set="main")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    layout = WorkspaceLayout(tmp_path)
    for project in ("cangjie_compiler", "cangjie_runtime"):
        Path(layout.worktree("main", project)).mkdir(parents=True)
    return tmp_path


def profiles() -> BranchSetProfile:
    return BranchSetProfile(
        manifest=lambda: MANIFEST,
        file_system=HostFileSystem(),
        read=read_record,
        render=render_record,
    )


def build_plan(root: Path, profile: Profile, names: tuple[str, ...] = ()):
    return BuildUnits(
        manifest=lambda: MANIFEST,
        executor=HostExecutor(),
        file_system=HostFileSystem(),
        host=lambda: HOST,
        lock=no_lock,
    ).plan(root, "main", profile=profile, names=names)


class TestTheRecord:
    def test_with_no_record_the_default_is_release(self, root: Path):
        # Act / Assert
        assert profiles().resolve(root, "main", None) is Profile.RELEASE

    def test_a_full_build_becomes_the_default(self, root: Path):
        # Arrange
        profiles().remember(build_plan(root, Profile.DEBUG))

        # Act / Assert
        assert profiles().resolve(root, "main", None) is Profile.DEBUG

    def test_a_partial_build_does_not_move_the_default(self, root: Path):
        # Arrange
        profiles().remember(build_plan(root, Profile.DEBUG))

        # Act
        profiles().remember(build_plan(root, Profile.RELEASE, ("runtime",)))

        # Assert: one unit rebuilt in another profile says nothing about
        # which SDK the branch set is.
        assert profiles().resolve(root, "main", None) is Profile.DEBUG

    def test_a_profile_named_on_the_command_line_wins(self, root: Path):
        # Arrange
        profiles().remember(build_plan(root, Profile.DEBUG))

        # Act / Assert
        assert profiles().resolve(root, "main", Profile.RELEASE) is Profile.RELEASE

    def test_the_story_that_motivated_it_is_refused(self, root: Path):
        # Arrange: built in debug, then only the compiler in release.
        profiles().remember(build_plan(root, Profile.DEBUG))

        # Act / Assert
        with pytest.raises(PreconditionError, match="runtime, stdlib"):
            profiles().check(build_plan(root, Profile.RELEASE, ("compiler",)))

    def test_a_partial_build_where_the_rest_is_built_goes_ahead(self, root: Path):
        # Arrange
        profiles().remember(build_plan(root, Profile.DEBUG))
        layout = WorkspaceLayout(root)
        for unit in ("runtime", "stdlib"):
            Path(layout.build_dir("main", "host", "release", unit)).mkdir(parents=True)

        # Act / Assert
        profiles().check(build_plan(root, Profile.RELEASE, ("compiler",)))


class TestTheFile:
    def test_a_table_cjdev_does_not_own_survives_a_write(self, tmp_path: Path):
        # Arrange: a later cjdev keeps the task beside the profile.
        path = tmp_path / "main.toml"
        path.write_text('[task]\nissue = "https://example.invalid/1"\n')

        # Act
        path.write_text(render_record(BranchSetRecord(Profile.DEBUG), path))

        # Assert
        text = path.read_text()
        assert 'issue = "https://example.invalid/1"' in text
        assert read_record(path).profile is Profile.DEBUG

    def test_a_missing_file_is_an_empty_record(self, tmp_path: Path):
        # Act / Assert
        assert read_record(tmp_path / "none.toml") == BranchSetRecord()

    def test_a_profile_cjdev_does_not_know_names_the_file(self, tmp_path: Path):
        # Arrange
        path = tmp_path / "main.toml"
        path.write_text('[build]\nprofile = "fast"\n')

        # Act / Assert
        with pytest.raises(PreconditionError) as refusal:
            read_record(path)
        assert refusal.value.remedy == f"delete {PurePath(path)}"
