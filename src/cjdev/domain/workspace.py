from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final

from cjdev.domain import Project


@final
@dataclass(frozen=True)
class WorkspaceId:
    value: str


@final
class Workspace:
    def __init__(self, id: WorkspaceId, state: "WorkspaceState | None") -> None:
        self._id = id
        self._state = UninitializedWorkspaceState() if state is None else state

    @property
    def id(self) -> WorkspaceId:
        return self._id

    def initialize(self) -> None:
        self._state.initialize(self)

    def _change_state(self, state: "WorkspaceState") -> None:
        self._state = state


class WorkspaceState(ABC):
    @abstractmethod
    def initialize(self, workspace: Workspace) -> None:
        pass


@final
class UninitializedWorkspaceState(WorkspaceState):
    def initialize(self, workspace: Workspace) -> None:
        workspace._change_state(InitializedWorkspaceState([]))


@final
class InitializedWorkspaceState(WorkspaceState):
    def __init__(self, projects: list[Project]) -> None:
        self._projects = projects

    def initialize(self, workspace: Workspace) -> None:
        pass


class WorkspaceRepo(ABC):
    @abstractmethod
    def get_by_id(self, id: WorkspaceId) -> Workspace:
        pass
