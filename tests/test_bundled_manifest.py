"""The manifest that ships in the wheel.

Loaded through `importlib.resources`, not from the working tree, so that a
packaging regression fails here rather than only for users who pip-installed.
"""

from pathlib import PurePosixPath

import pytest

from cjdev.domain.build import CopyStep, RunStep
from cjdev.domain.manifest import Manifest, ProjectRole
from cjdev.errors import ManifestError
from cjdev.infra.config import (
    SUPPORTED_SCHEMA_VERSION,
    load_bundled_manifest,
    parse_manifest,
)

PROJECTS = [
    "cangjie_compiler",
    "cangjie_runtime",
    "cangjie_stdx",
    "cangjie_tools",
    "cangjie_test_framework",
    "cangjie_test",
    "cangjie_multiplatform_interop",
]

UNITS = ["compiler", "runtime", "stdlib", "stdx", "cjpm"]


@pytest.fixture
def bundled() -> Manifest:
    return load_bundled_manifest()


def test_ships_every_project_of_the_set(bundled: Manifest):
    assert [str(p.name) for p in bundled.projects] == PROJECTS


def test_every_project_records_its_own_default_branch(bundled: Manifest):
    # They all happen to be `main`, and that stays data.
    assert all(p.default_branch == "main" for p in bundled.projects)


def test_the_test_projects_build_nothing(bundled: Manifest):
    assert bundled.project("cangjie_test_framework").role is (ProjectRole.TEST_RUNNER)
    assert bundled.project("cangjie_test").role is ProjectRole.TEST_DATA
    assert bundled.units_of("cangjie_test") == ()


def test_ships_only_the_units_whose_edges_are_settled(bundled: Manifest):
    # Unverified edges are absent, not guessed: cangjie_tools holds nine more
    # tools, and they land here when their build scripts have been read.
    assert [u.name for u in bundled.build_units] == UNITS


def test_the_interop_project_contributes_no_edges_yet(bundled: Manifest):
    # It is still cloned and branched like any other project.
    assert bundled.units_of("cangjie_multiplatform_interop") == ()


def test_one_project_can_hold_several_build_units(bundled: Manifest):
    assert [u.name for u in bundled.units_of("cangjie_runtime")] == [
        "runtime",
        "stdlib",
    ]


def test_the_whole_sdk_builds_in_dependency_order(bundled: Manifest):
    assert [u.name for u in bundled.build_order()] == UNITS


def test_build_unit_paths_locate_their_build_script(bundled: Manifest):
    assert str(bundled.unit("compiler").path) == "."
    assert str(bundled.unit("cjpm").path) == "cjpm"


class TestSchemaVersion:
    def test_the_bundled_manifest_is_the_supported_version(self, bundled: Manifest):
        assert bundled.schema_version == SUPPORTED_SCHEMA_VERSION

    def test_a_future_version_is_refused_with_an_actionable_message(self):
        # Refuse, do not best-effort parse.
        with pytest.raises(ManifestError, match="Upgrade cjdev"):
            parse_manifest("schema_version = 99", source="test")


class TestParseErrors:
    def test_a_missing_key_names_the_key_and_where(self):
        toml = """
        schema_version = 2
        [projects.a]
        role = "buildable"
        upstream = "https://example.invalid/a.git"
        """

        with pytest.raises(
            ManifestError, match=r"project a is missing.*default_branch"
        ):
            parse_manifest(toml, source="test")

    def test_an_unknown_role_lists_the_known_ones(self):
        toml = """
        schema_version = 2
        [projects.a]
        role = "wat"
        upstream = "https://example.invalid/a.git"
        default_branch = "main"
        """

        with pytest.raises(ManifestError, match="Known roles"):
            parse_manifest(toml, source="test")

    def test_a_top_level_key_of_the_wrong_type_is_refused_naming_the_key(self):
        # A string where a table belongs is otherwise an AttributeError at
        # the first `.items()` - a traceback, not a refusal.
        with pytest.raises(ManifestError, match=r"projects must be a table"):
            parse_manifest(
                """
                schema_version = 2
                projects = "x"
                """,
                source="test",
            )

    def test_broken_toml_is_reported_as_such(self):
        with pytest.raises(ManifestError, match="not valid TOML"):
            parse_manifest("schema_version = = 1", source="test")

    def test_depends_on_written_as_a_string_is_refused_at_parse_time(self):
        # The bundled parser shares the guard: iterated one character at a
        # time, "compiler" would surface as unknown one-letter build units,
        # far from the line that caused it.
        toml = """
        schema_version = 2
        [projects.compiler]
        role = "buildable"
        upstream = "https://example.invalid/compiler.git"
        default_branch = "main"
        [build_units.compiler]
        project = "compiler"
        path = "."
        depends_on = "runtime"
        """

        with pytest.raises(
            ManifestError,
            match=r"build unit compiler depends_on must be an array",
        ):
            parse_manifest(toml, source="test")


class TestGroups:
    def test_the_default_group_is_the_minimal_sdk(self, bundled: Manifest):
        # stdx is in it because `cjpm` refuses to build without
        # CANGJIE_STDX_PATH, so a set with cjpm and no stdx cannot be built.
        assert [p.name for p in bundled.default_projects()] == [
            "cangjie_compiler",
            "cangjie_runtime",
            "cangjie_stdx",
            "cangjie_tools",
        ]

    def test_the_testing_group_includes_an_sdk_to_test(self, bundled: Manifest):
        # cangjie_test_framework builds nothing and cangjie_test is data for
        # it, so those two alone would be a runner with nothing to point at.
        testing = {p.name for p in bundled.group("testing")}

        assert {p.name for p in bundled.default_projects()} <= testing
        assert "cangjie_test_framework" in testing

    def test_every_group_member_is_a_real_project(self, bundled: Manifest):
        known = {p.name for p in bundled.projects}

        for members in bundled.groups.values():
            assert set(members) <= known


def test_unit_names_are_the_flat_token_the_cli_takes(bundled: Manifest):
    # `cjdev build stdlib`, not `cjdev build cangjie_runtime/stdlib`. Which
    # project holds a unit is recorded separately, so the name stays typeable.
    assert all("/" not in unit.name for unit in bundled.build_units)
    assert len({unit.name for unit in bundled.build_units}) == len(bundled.build_units)


class TestBuildData:
    def test_every_shipped_unit_can_be_built(self, bundled: Manifest):
        # Arrange / Act / Assert: a unit with no argv is a name `cjdev build`
        # can only refuse.
        assert all(unit.build for unit in bundled.build_units)
        assert all(unit.scratch for unit in bundled.build_units)

    def test_the_projects_that_track_build_do_not_redirect_it(self, bundled: Manifest):
        # `cangjie_runtime/runtime/build` and `cangjie_stdx/build` hold cmake
        # toolchain files, so a uniform `build` entry would delete them.
        for name in ("runtime", "stdx"):
            assert PurePosixPath("build") not in bundled.unit(name).scratch

    def test_the_compiler_is_told_the_profile_and_the_job_count(
        self, bundled: Manifest
    ):
        assert "{profile}" in bundled.unit("compiler").build
        assert "{jobs}" in bundled.unit("compiler").build

    def test_cjpm_installs_by_copying_into_two_directories(self, bundled: Manifest):
        # Its binary belongs in tools/bin and its repo config in tools/config;
        # sharing a directory makes cjpm fall back to an empty config silently.
        steps = bundled.unit("cjpm").install

        assert [step.into for step in steps if isinstance(step, CopyStep)] == [
            "{dist}/tools/bin",
            "{dist}/tools/config",
        ]

    def test_the_cmake_units_run_their_own_install(self, bundled: Manifest):
        for name in ("compiler", "stdlib", "stdx"):
            assert all(isinstance(step, RunStep) for step in bundled.unit(name).install)

    def test_cjpm_cannot_be_scheduled_before_stdx(self, bundled: Manifest):
        # It refuses to build without CANGJIE_STDX_PATH.
        order = [unit.name for unit in bundled.build_order(["cjpm"])]

        assert order.index("stdx") < order.index("cjpm")

    def test_nothing_ships_an_extra_arg(self, bundled: Manifest):
        # Machine-specific flags belong to a workspace, not to the wheel.
        assert all(unit.extra_args == () for unit in bundled.build_units)
