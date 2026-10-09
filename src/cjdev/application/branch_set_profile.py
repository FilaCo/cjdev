"""Which profile a branch set is in, for every command that has to pick one.

The profile of its last full build, remembered in the branch set's record.
Defaulting to release regardless is how a debug SDK got a release `cjc` built
beside an empty release dist: every command after it would have tested a
compiler that could not import `std`.
"""

from collections.abc import Callable, Sequence
from pathlib import Path, PurePath
from typing import final

from cjdev.application.build_units import BuildPlan
from cjdev.application.ports import FileSystem
from cjdev.application.report_status import ManifestProvider
from cjdev.domain.build import Profile
from cjdev.domain.environment import DEFAULT_ENVIRONMENT, Environment
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.record import BranchSetRecord
from cjdev.errors import PreconditionError

ReadRecord = Callable[[PurePath], BranchSetRecord]
RenderRecord = Callable[[BranchSetRecord, PurePath], str]


def unbuilt(
    selected: Sequence[str], units: Sequence[str], built: frozenset[str]
) -> tuple[str, ...]:
    """The units a partial build leaves to whatever is already in the dist.

    Every unit outside the selection, not only its dependencies: a fresh
    compiler alone in a dist with no stdlib is an SDK that compiles nothing,
    and nothing in the build graph says the compiler needs stdlib.
    """
    chosen = set(selected)
    return tuple(unit for unit in units if unit not in chosen and unit not in built)


def check_profile(
    profile: Profile,
    remembered: Profile | None,
    missing: Sequence[str],
    *,
    branch_set: str,
) -> None:
    if remembered is None or profile is remembered or not missing:
        return
    raise PreconditionError(
        f"branch set {branch_set} is built in {remembered}, and {profile} has "
        f"no build of {', '.join(missing)}; this build would leave a {profile} "
        f"SDK that cannot compile anything.",
        remedy=f"cjdev build -p {profile}",
    )


@final
class BranchSetProfile:
    def __init__(
        self,
        manifest: ManifestProvider,
        file_system: FileSystem,
        read: ReadRecord,
        render: RenderRecord,
        environment: Environment = DEFAULT_ENVIRONMENT,
    ) -> None:
        self._manifest = manifest
        self._fs = file_system
        self._read = read
        self._render = render
        self._environment = environment

    def resolve(self, root: Path, branch_set: str, chosen: Profile | None) -> Profile:
        if chosen is not None:
            return chosen
        return self._record(root, branch_set).default_profile()

    def check(self, plan: BuildPlan) -> None:
        """Refuse a partial build in a profile the rest of the SDK is not
        built in. Before anything moves, so a refusal costs nothing."""
        layout = WorkspaceLayout(plan.root)
        where = self._environment.mode.value
        units = [unit.name for unit in self._manifest().build_units]
        built = frozenset(
            unit
            for unit in units
            if Path(
                layout.build_dir(plan.branch_set, where, plan.profile.value, unit)
            ).is_dir()
        )
        check_profile(
            plan.profile,
            self._record(Path(plan.root), plan.branch_set).profile,
            unbuilt([unit.unit for unit in plan.units], units, built),
            branch_set=plan.branch_set,
        )

    def remember(self, plan: BuildPlan) -> None:
        """After a build that succeeded. Only a full one moves the default: a
        single unit rebuilt in another profile says nothing about which SDK
        the branch set is."""
        units = {unit.name for unit in self._manifest().build_units}
        if {unit.unit for unit in plan.units} != units:
            return
        path = WorkspaceLayout(plan.root).record(plan.branch_set)
        record = BranchSetRecord(profile=plan.profile)
        self._fs.mkdir(path.parent)
        self._fs.write_text(path, self._render(record, path))

    def _record(self, root: Path, branch_set: str) -> BranchSetRecord:
        return self._read(WorkspaceLayout(root).record(branch_set))
