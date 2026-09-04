"""Grouping worktrees into branch sets, with no repository in sight (NFR-2)."""

from pathlib import PurePath

from cjdev.domain.state import Checkout, active_branch_set, branch_sets_of

ROOT = PurePath("/ws")


def checkout(project: str, directory: str, branch: str | None = "fix/ice") -> Checkout:
    return Checkout(
        project=project,
        path=ROOT / directory / project,
        branch=branch,
        head="0" * 40,
        dirty=False,
        tracking=(),
    )


class TestBranchSetsComeFromGitNotFromDirectories:
    def test_worktrees_in_one_directory_are_one_branch_set(self):
        sets = branch_sets_of(
            ROOT, [checkout("alpha", "fix-ice"), checkout("beta", "fix-ice")]
        )

        assert len(sets) == 1
        assert [c.project for c in sets[0].checkouts] == ["alpha", "beta"]

    def test_the_name_is_the_branch_not_the_directory(self):
        # CFG-9: flattening is one-way, so `fix-ice` on disk cannot say
        # whether the branch is `fix/ice` or `fix-ice`. git can.
        sets = branch_sets_of(ROOT, [checkout("alpha", "fix-ice")])

        assert sets[0].name == "fix/ice"
        assert sets[0].directory == ROOT / "fix-ice"

    def test_an_all_detached_branch_set_falls_back_to_the_directory(self):
        # Every project still on its pinned base ref (§4.2): there is no
        # branch anywhere to read the real name off.
        sets = branch_sets_of(ROOT, [checkout("alpha", "fix-ice", branch=None)])

        assert sets[0].name == "fix-ice"

    def test_one_enrolled_project_is_enough_to_name_the_set(self):
        # BRANCH-6 enrols lazily, so a set is normally a mix.
        sets = branch_sets_of(
            ROOT,
            [checkout("alpha", "fix-ice", branch=None), checkout("beta", "fix-ice")],
        )

        assert sets[0].name == "fix/ice"

    def test_sets_are_ordered_by_directory_not_by_arrival(self):
        # PAR-4: the fan-out that produced these must not decide the order
        # they are printed in.
        sets = branch_sets_of(
            ROOT, [checkout("alpha", "main"), checkout("alpha", "fix-ice")]
        )

        assert [s.directory.name for s in sets] == ["fix-ice", "main"]

    def test_a_worktree_outside_the_root_is_not_a_branch_set(self):
        # git reported it, but cjdev did not lay it out - this is the stray
        # checkout `clean` refuses to break silently (R9).
        stray = Checkout(
            project="alpha",
            path=PurePath("/elsewhere/hand-made/alpha"),
            branch="fix/ice",
            head="0" * 40,
            dirty=False,
            tracking=(),
        )

        assert branch_sets_of(ROOT, [stray]) == ()

    def test_a_worktree_nested_deeper_than_one_level_is_not_one_either(self):
        # The root holds branch sets and nothing else (§4.1); anything deeper
        # is something a person made by hand.
        deep = checkout("alpha", "fix-ice/extra")

        assert branch_sets_of(ROOT, [deep]) == ()


class TestActiveBranchSet:
    def test_standing_inside_a_worktree_selects_its_branch_set(self):
        sets = branch_sets_of(ROOT, [checkout("alpha", "fix-ice")])

        active = active_branch_set(ROOT, ROOT / "fix-ice" / "alpha" / "src", sets)

        assert active == "fix/ice"

    def test_standing_at_the_root_selects_nothing(self):
        sets = branch_sets_of(ROOT, [checkout("alpha", "fix-ice")])

        assert active_branch_set(ROOT, ROOT, sets) is None

    def test_standing_outside_the_workspace_selects_nothing(self):
        sets = branch_sets_of(ROOT, [checkout("alpha", "fix-ice")])

        assert active_branch_set(ROOT, PurePath("/tmp/elsewhere"), sets) is None

    def test_a_stray_directory_in_the_root_is_not_a_branch_set(self):
        # CFG-9: a directory a user made in the root is not one, so standing
        # in it must not name one either.
        sets = branch_sets_of(ROOT, [checkout("alpha", "fix-ice")])

        assert active_branch_set(ROOT, ROOT / "notes", sets) is None
