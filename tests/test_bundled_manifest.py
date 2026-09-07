"""The manifest that ships in the wheel.

Loaded through `importlib.resources`, not from the working tree, so that a
packaging regression fails here rather than only for users who pip-installed.
"""

import pytest

from cjdev.domain.manifest import Manifest, ProjectRole
from cjdev.errors import ManifestError
from cjdev.infra.config import (
    SUPPORTED_SCHEMA_VERSION,
    load_bundled_manifest,
    parse_manifest,
)

SIX_PROJECTS = [
    "cangjie_compiler",
    "cangjie_runtime",
    "cangjie_tools",
    "cangjie_test_framework",
    "cangjie_test",
    "cangjie_multiplatform_interop",
]


@pytest.fixture
def bundled() -> Manifest:
    return load_bundled_manifest()


def test_ships_the_six_projects_of_section_43(bundled: Manifest):
    assert [str(p.name) for p in bundled.projects] == SIX_PROJECTS


def test_every_project_records_its_own_default_branch(bundled: Manifest):
    # They all happen to be `main`, and that stays data.
    assert all(p.default_branch == "main" for p in bundled.projects)


def test_the_test_projects_build_nothing(bundled: Manifest):
    assert bundled.project("cangjie_test_framework").role is (ProjectRole.TEST_RUNNER)
    assert bundled.project("cangjie_test").role is ProjectRole.TEST_DATA
    assert bundled.units_of("cangjie_test") == ()


def test_ships_only_the_four_confirmed_build_units(bundled: Manifest):
    # R11: unverified edges are absent, not guessed. `cjdev build` offers nine
    # more names; they land here when question A says where they live.
    assert [u.name for u in bundled.build_units] == [
        "compiler",
        "runtime",
        "stdlib",
        "cjpm",
    ]


def test_the_interop_project_contributes_no_edges_yet(bundled: Manifest):
    # Question A. It is still cloned and branched like any other project.
    assert bundled.units_of("cangjie_multiplatform_interop") == ()


def test_one_project_can_hold_several_build_units(bundled: Manifest):
    assert [u.name for u in bundled.units_of("cangjie_runtime")] == [
        "runtime",
        "stdlib",
    ]


def test_the_whole_sdk_builds_in_the_order_section_43_states(bundled: Manifest):
    assert [u.name for u in bundled.build_order()] == [
        "compiler",
        "runtime",
        "stdlib",
        "cjpm",
    ]


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
        schema_version = 1
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
        schema_version = 1
        [projects.a]
        role = "wat"
        upstream = "https://example.invalid/a.git"
        default_branch = "main"
        """

        with pytest.raises(ManifestError, match="Known roles"):
            parse_manifest(toml, source="test")

    def test_broken_toml_is_reported_as_such(self):
        with pytest.raises(ManifestError, match="not valid TOML"):
            parse_manifest("schema_version = = 1", source="test")


class TestGroups:
    def test_the_default_group_is_the_minimal_sdk(self, bundled: Manifest):
        assert [p.name for p in bundled.default_projects()] == [
            "cangjie_compiler",
            "cangjie_runtime",
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
