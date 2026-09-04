"""The build graph is manifest data, so these tests build their own manifests.

Nothing here reads the shipped default manifest - that is what
`test_bundled_manifest` is for. Mixing the two would make a graph bug look
like a data bug, and vice versa.
"""

from pathlib import PurePosixPath

import pytest

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
        name=name,
        project=owner,
        path=PurePosixPath("."),
        depends_on=tuple(deps),
    )


def manifest(*, projects: list[Project], units: list[BuildUnit]) -> Manifest:
    return Manifest(
        schema_version=1, projects=tuple(projects), build_units=tuple(units)
    )


@pytest.fixture
def sdk() -> Manifest:
    """The confirmed part of §4.3, with the diamond that matters."""
    return manifest(
        projects=[project("compiler"), project("runtime"), project("tools")],
        units=[
            unit("compiler", "compiler"),
            unit("runtime", "runtime"),
            unit("stdlib", "runtime", "compiler", "runtime"),
            unit("cjpm", "tools", "compiler", "runtime", "stdlib"),
        ],
    )


def ids(units: tuple[BuildUnit, ...]) -> list[str]:
    return [str(u.name) for u in units]


class TestBuildOrder:
    def test_orders_the_whole_graph_by_dependency(self, sdk: Manifest):
        order = ids(sdk.build_order())

        assert order.index("compiler") < order.index("stdlib")
        assert order.index("runtime") < order.index("stdlib")
        assert order.index("stdlib") < order.index("cjpm")

    def test_breaks_ties_by_manifest_order(self):
        # Two independent units: nothing but declaration order can decide,
        # and PAR-4 requires that the decision be the same every run.
        graph = manifest(
            projects=[project("a"), project("b")],
            units=[unit("b", "b"), unit("a", "a")],
        )

        assert ids(graph.build_order()) == ["b", "a"]

    def test_selecting_a_unit_pulls_in_its_dependencies(self, sdk: Manifest):
        # `--upto runtime/stdlib` (BUILD-2): the unit and what it needs, and
        # explicitly not cjpm, which needs *it*.
        order = ids(sdk.build_order(["stdlib"]))

        assert order == ["compiler", "runtime", "stdlib"]

    def test_selection_is_deduplicated(self, sdk: Manifest):
        order = ids(sdk.build_order(["stdlib", "compiler"]))

        assert order == ["compiler", "runtime", "stdlib"]

    def test_rejects_a_cycle_naming_the_units_involved(self):
        graph = manifest(
            projects=[project("p")],
            units=[unit("a", "p", "b"), unit("b", "p", "a")],
        )

        with pytest.raises(ManifestError, match="cycle"):
            graph.build_order()

    def test_rejects_an_unknown_selection_listing_what_exists(self, sdk: Manifest):
        with pytest.raises(ManifestError, match="unknown build unit"):
            sdk.build_order(["nope"])


class TestDependents:
    def test_returns_the_unit_and_everything_downstream_in_build_order(
        self, sdk: Manifest
    ):
        # `--from runtime/runtime`: what a change to it forces to rebuild.
        assert ids(sdk.dependents_of("runtime")) == [
            "compiler",
            "runtime",
            "stdlib",
            "cjpm",
        ]

    def test_a_leaf_dependent_is_just_itself_and_its_dependencies(self, sdk: Manifest):
        assert ids(sdk.dependents_of("cjpm")) == [
            "compiler",
            "runtime",
            "stdlib",
            "cjpm",
        ]


class TestLookup:
    def test_units_of_a_project_with_several(self, sdk: Manifest):
        assert ids(sdk.units_of("runtime")) == [
            "runtime",
            "stdlib",
        ]

    def test_a_project_that_builds_nothing_has_no_units(self):
        graph = manifest(projects=[project("cases", ProjectRole.TEST_DATA)], units=[])

        assert graph.units_of("cases") == ()

    def test_unknown_project_is_reported_with_the_known_ones(self, sdk: Manifest):
        with pytest.raises(ManifestError, match="compiler, runtime, tools"):
            sdk.project("nope")


class TestValidation:
    def test_rejects_a_duplicate_project(self):
        with pytest.raises(ManifestError, match="declared more than once"):
            manifest(projects=[project("a"), project("a")], units=[])

    def test_rejects_a_duplicate_build_unit(self):
        with pytest.raises(ManifestError, match="declared more than once"):
            manifest(projects=[project("a")], units=[unit("u", "a"), unit("u", "a")])

    def test_rejects_a_unit_owned_by_an_unknown_project(self):
        with pytest.raises(ManifestError, match="unknown project"):
            manifest(projects=[project("a")], units=[unit("u", "ghost")])

    def test_rejects_a_dependency_on_an_unknown_unit(self):
        with pytest.raises(ManifestError, match="unknown unit"):
            manifest(projects=[project("a")], units=[unit("u", "a", "ghost")])

    def test_rejects_a_unit_depending_on_itself(self):
        with pytest.raises(ManifestError, match="depends on itself"):
            manifest(projects=[project("a")], units=[unit("u", "a", "u")])
