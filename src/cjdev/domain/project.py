from dataclasses import dataclass
from enum import Enum, auto, unique
from typing import final


@final
@unique
class ProjectRole(Enum):
    BUILDABLE = auto()
    TEST_RUNNER = auto()
    TEST_DATA = auto()


@final
@dataclass(frozen=True)
class ProjectSpec:
    role: ProjectRole
    upstream_url: str
    default_branch: str


@final
@dataclass(frozen=True)
class ProjectId:
    value: str


@final
class Project:
    def __init__(self, id: ProjectId, spec: ProjectSpec, origin_url: str) -> None:
        self._id = id
        self._spec = spec
        self._origin_url = origin_url
