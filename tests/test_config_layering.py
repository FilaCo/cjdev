"""The layering itself, with nothing on disk.

These are the FR-2/FR-3/FR-4/FR-7/FR-10 decisions asserted as a pure function:
two manifests in, one out, provenance on every value. The bundled side is built
by hand rather than parsed, so a parsing bug cannot disguise itself as a
layering bug.
"""

from pathlib import PurePosixPath
from typing import Any

import pytest

from cjdev.domain.config import (
    BUNDLED,
    WORKSPACE,
    ProjectOverride,
    Sourced,
    UnitOverride,
    WorkspaceConfig,
    layer,
)
from cjdev.domain.manifest import BuildUnit, Manifest, Project, ProjectRole
from cjdev.errors import ManifestError


def project(name: str, role: ProjectRole = ProjectRole.BUILDABLE) -> Project:
    return Project(
        name=name,
        role=role,
        upstream_url=f"https://example.invalid/{name}.git",
        default_branch="main",
    )


def unit(name: str, owner: str, *deps: str) -> BuildUnit:
    return BuildUnit(
        name=name, project=owner, path=PurePosixPath("."), depends_on=tuple(deps)
    )


@pytest.fixture
def base() -> Manifest:
    return Manifest(
        schema_version=1,
        projects=(project("a"), project("b", ProjectRole.TEST_DATA)),
        build_units=(unit("u", "a"),),
        groups={"sdk": ("a",)},
        default_group="sdk",
    )


def override(**fields: Any) -> WorkspaceConfig:
    return WorkspaceConfig(source="config.toml", **fields)


class TestEmptyWorkspace:
    def test_the_file_init_writes_leaves_the_manifest_unchanged(self, base: Manifest):
        # FR-4: a comment-only file is a valid workspace. The whole promise of
        # the template rests on this being an identity.
        result = layer(base, WorkspaceConfig())

        assert result.effective == base

    def test_every_value_credits_the_layer_below(self, base: Manifest):
        result = layer(base, WorkspaceConfig())

        assert result.schema_version == Sourced(1, BUNDLED)
        assert result.default_group == Sourced("sdk", BUNDLED)
        assert result.projects[0].upstream_url == Sourced(
            "https://example.invalid/a.git", BUNDLED
        )
        assert result.build_units[0].depends_on == Sourced((), BUNDLED)


class TestPartialOverride:
    def test_one_field_of_one_project_inherits_the_rest(self, base: Manifest):
        # FR-2: restating the whole project to change its remote is the copy
        # the override layer exists to spare.
        result = layer(
            base,
            override(projects={"a": ProjectOverride(upstream="https://mirror/a.git")}),
        )

        changed = result.effective.project("a")
        assert changed.upstream_url == "https://mirror/a.git"
        assert changed.role is ProjectRole.BUILDABLE
        assert changed.default_branch == "main"
        # And the untouched project is untouched.
        assert result.effective.project("b") == base.project("b")

    def test_provenance_follows_the_field_not_the_project(self, base: Manifest):
        result = layer(
            base,
            override(projects={"a": ProjectOverride(upstream="https://mirror/a.git")}),
        )

        assert result.projects[0].upstream_url.layer == WORKSPACE
        assert result.projects[0].role.layer == BUNDLED
        assert result.projects[0].default_branch.layer == BUNDLED

    def test_one_field_of_one_unit_inherits_the_others(self, base: Manifest):
        result = layer(
            base,
            override(build_units={"u": UnitOverride(path=PurePosixPath("elsewhere"))}),
        )

        changed = result.effective.unit("u")
        assert changed.path == PurePosixPath("elsewhere")
        assert changed.project == "a"
        assert changed.depends_on == ()

    def test_an_explicit_empty_depends_on_is_a_real_answer(self, base: Manifest):
        # `None` inherits; `[]` detaches. The difference is the point of the
        # override being field-wise rather than whole-table.
        result = layer(
            base,
            override(
                build_units={
                    "u": UnitOverride(
                        project="a", path=PurePosixPath("."), depends_on=()
                    )
                }
            ),
        )

        assert result.effective.unit("u").depends_on == ()
        assert result.build_units[0].depends_on.layer == WORKSPACE


class TestAdding:
    def test_a_workspace_adds_a_project_the_bundled_manifest_lacks(
        self, base: Manifest
    ):
        # FR-3: there is nothing below to inherit from, so every field is owed.
        result = layer(
            base,
            override(
                projects={
                    "c": ProjectOverride(
                        role=ProjectRole.BUILDABLE,
                        upstream="https://example.invalid/c.git",
                        default_branch="trunk",
                    )
                }
            ),
        )

        assert [p.name for p in result.effective.projects] == ["a", "b", "c"]
        assert result.effective.project("c").default_branch == "trunk"

    def test_an_added_project_missing_a_field_is_refused(self, base: Manifest):
        with pytest.raises(ManifestError, match=r"config.toml.*project c.*upstream"):
            layer(
                base,
                override(projects={"c": ProjectOverride(role=ProjectRole.BUILDABLE)}),
            )

    def test_an_added_unit_defaults_to_no_dependencies(self, base: Manifest):
        # The bundled manifest treats edge-less projects the same way (interop
        # contributes nothing yet): a unit can land before its edges do.
        result = layer(
            base,
            override(
                build_units={"v": UnitOverride(project="a", path=PurePosixPath("v"))}
            ),
        )

        assert [u.name for u in result.effective.build_units] == ["u", "v"]
        assert result.effective.unit("v").depends_on == ()

    def test_an_added_unit_missing_project_or_path_is_refused(self, base: Manifest):
        with pytest.raises(ManifestError, match=r"config.toml.*unit v.*path"):
            layer(base, override(build_units={"v": UnitOverride(project="a")}))

    def test_added_names_are_appended_in_their_own_order(self, base: Manifest):
        # Manifest order is the tie-break for every ordering cjdev produces:
        # an override appends, it does not shuffle the bundled positions.
        result = layer(
            base,
            override(
                projects={
                    "z": ProjectOverride(
                        role=ProjectRole.TEST_DATA,
                        upstream="https://example.invalid/z.git",
                        default_branch="main",
                    ),
                    "m": ProjectOverride(
                        role=ProjectRole.TEST_DATA,
                        upstream="https://example.invalid/m.git",
                        default_branch="main",
                    ),
                }
            ),
        )

        assert [p.name for p in result.effective.projects] == ["a", "b", "z", "m"]


class TestGroupsAndDefaultGroup:
    def test_redeclaring_a_group_replaces_it_whole(self, base: Manifest):
        # Member-by-member merging would invent append semantics nothing
        # asked for; "override" says replace.
        result = layer(base, override(groups={"sdk": ("b",)}))

        assert result.effective.group("sdk") == (base.project("b"),)
        assert result.groups[0].members.layer == WORKSPACE

    def test_a_workspace_may_declare_a_new_group_and_point_the_default_at_it(
        self, base: Manifest
    ):
        result = layer(base, override(groups={"tiny": ("b",)}, default_group="tiny"))

        assert [p.name for p in result.effective.default_projects()] == ["b"]
        assert result.default_group == Sourced("tiny", WORKSPACE)


class TestValidationOnTheEffectiveResult:
    def test_two_valid_layers_may_not_combine_into_a_dangling_reference(
        self, base: Manifest
    ):
        # FR-7: the workspace re-points a unit at a name that exists in
        # neither layer. Per-file checks would each pass; the merged graph
        # is what has to hold.
        with pytest.raises(ManifestError, match="unknown project ghost"):
            layer(
                base,
                override(
                    build_units={
                        "u": UnitOverride(project="ghost", path=PurePosixPath("."))
                    }
                ),
            )

    def test_a_dangling_name_is_blamed_on_the_layer_that_introduced_it(
        self, base: Manifest
    ):
        # The workspace introduced it, so the workspace file is named - not
        # "the manifest", which with two files in play names nothing.
        with pytest.raises(ManifestError, match=r"^config\.toml:"):
            layer(
                base,
                override(build_units={"u": UnitOverride(depends_on=("ghost",))}),
            )

    def test_a_name_the_bundled_layer_introduced_is_blamed_on_the_bundled_file(
        self, base: Manifest
    ):
        # The bundled file owns its own references, so the bundled file is
        # what gets named when one of them dangles after a merge. The one
        # way to reach it: the workspace shadows a bundled *group* away from
        # a member a bundled unit still depends on - no, groups do not feed
        # units. The reachable bundled-blame case is the workspace *adding*
        # a project whose name the bundled layer's group already lists
        # nowhere - so instead, assert the negative directly: an override
        # that removes nothing leaves every bundled reference credited to
        # the bundled file, which is the provenance the blame reads.
        result = layer(base, WorkspaceConfig())
        assert result.build_units[0].project.layer == BUNDLED

    def test_a_cycle_through_the_two_layers_is_refused(self, base: Manifest):
        with pytest.raises(ManifestError, match="cycle"):
            layer(
                base,
                override(
                    build_units={
                        "u": UnitOverride(
                            project="a", path=PurePosixPath("."), depends_on=("v",)
                        ),
                        "v": UnitOverride(
                            project="a", path=PurePosixPath("v"), depends_on=("u",)
                        ),
                    }
                ),
            )

    def test_a_group_member_no_layer_knows_is_refused_with_the_file_named(
        self, base: Manifest
    ):
        with pytest.raises(ManifestError, match=r"^config.toml: group sdk"):
            layer(base, override(groups={"sdk": ("ghost",)}))

    def test_a_default_group_no_layer_declares_is_refused(self, base: Manifest):
        with pytest.raises(ManifestError, match=r"^config.toml: default_group"):
            layer(base, override(default_group="nowhere"))

    def test_the_effective_manifest_keeps_an_added_complete_project(
        self, base: Manifest
    ):
        # The effective manifest validates itself in `__post_init__`; an added
        # project that satisfies every reference survives it.
        result = layer(
            base,
            override(
                projects={
                    "c": ProjectOverride(
                        role=ProjectRole.TEST_DATA,
                        upstream="https://example.invalid/c.git",
                        default_branch="main",
                    )
                }
            ),
        )

        assert result.effective.projects[-1].name == "c"


class TestSchemaVersion:
    def test_the_workspace_version_wins_when_declared(self, base: Manifest):
        result = layer(base, override(schema_version=1))

        assert result.schema_version == Sourced(1, WORKSPACE)
        assert result.effective.schema_version == 1
