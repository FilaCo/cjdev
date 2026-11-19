"""Select and inspect the third-party inputs of one branch set."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePath

from cjdev.application.branch_set_profile import ReadRecord
from cjdev.application.third_party import observe
from cjdev.domain.config import LayeredManifest
from cjdev.domain.dependencies import Selection, effective
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import BuildUnit, ThirdParty
from cjdev.errors import PreconditionError


@dataclass(frozen=True)
class DependencyRequest:
    unit: str
    name: str
    ref: str | None
    upstream: str | None = None

    def validate(self, unit: BuildUnit) -> None:
        names = [source.name for source in unit.third_party]
        if self.name not in names:
            known = ", ".join(names) or "none"
            raise PreconditionError(
                f"Unknown dependency {self.name} for {unit.name}. "
                f"Known dependencies: {known}."
            )
        if names.count(self.name) > 1:
            raise PreconditionError(
                f"Multiple dependencies in {unit.name} are named {self.name}."
            )
        if any(
            value is not None and not value.strip()
            for value in (self.ref, self.upstream)
        ):
            raise PreconditionError("A dependency ref and upstream must be non-empty.")

    def decide(self, previous: Selection | None) -> Selection | None:
        if self.ref is None:
            return None
        upstream = (
            self.upstream
            if self.upstream is not None or previous is None
            else previous.upstream
        )
        return Selection(self.ref, upstream)


@dataclass(frozen=True)
class DependencyRow:
    unit: str
    source: ThirdParty
    linked: str | None
    origin: str


EditDependency = Callable[
    [PurePath, str, str, Callable[[Selection | None], Selection | None]],
    Selection | None,
]


class ManageDependencies:
    def __init__(
        self,
        layout: WorkspaceLayout,
        branch_set: str,
        manifest: LayeredManifest,
        read: ReadRecord,
        edit: EditDependency,
    ) -> None:
        self._layout = layout
        self._branch_set = branch_set
        self._manifest = manifest
        self._record = layout.record(branch_set)
        self._read = read
        self._edit = edit

    def run(self, request: DependencyRequest | None = None) -> list[DependencyRow]:
        if request is None:
            choices = self._read(self._record).dependencies
        else:
            request.validate(self._manifest.effective.unit(request.unit))
            # Decide from the value under the writer's lock: a simultaneous
            # ref-only edit must retain the upstream selected before it.
            selected = self._edit(
                self._record, request.unit, request.name, request.decide
            )
            choices = (
                {} if selected is None else {(request.unit, request.name): selected}
            )

        rows = []
        for layers in self._manifest.build_units:
            if request is not None and request.unit != layers.name:
                continue
            unit = self._manifest.effective.unit(layers.name)
            seen = observe(self._layout, self._branch_set, unit)
            for source, link in zip(unit.third_party, seen, strict=True):
                if request is not None and request.name != source.name:
                    continue
                origin = (
                    self._branch_set
                    if (unit.name, source.name) in choices
                    else layers.third_party.layer
                )
                rows.append(
                    DependencyRow(
                        unit.name,
                        effective(unit.name, source, choices),
                        link.commit,
                        origin,
                    )
                )
        return rows
