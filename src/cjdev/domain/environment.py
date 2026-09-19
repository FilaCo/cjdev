"""Where a build runs, and what runs it.

A workspace property rather than a flag, because the answer decides the target
a build produces, the toolchain it produces it with and the directories it
writes into. Two invocations of one workspace disagreeing about it would be
two SDKs under one prefix.

Defaulting to the host is what keeps every workspace that predates this
section, and every one that never answers the question, building the way it
always has.
"""

from dataclasses import dataclass
from enum import Enum, unique
from typing import final


@final
@unique
class Mode(Enum):
    HOST = "host"
    CONTAINER = "container"

    def __str__(self) -> str:
        return self.value


@final
@unique
class Runtime(Enum):
    """Read only under `Mode.CONTAINER`, and answered anyway: the two differ by
    more than their program name, so a workspace that switches modes must not
    also have to discover that it never said which runtime it has."""

    DOCKER = "docker"
    PODMAN = "podman"

    def __str__(self) -> str:
        return self.value


@final
@dataclass(frozen=True)
class Environment:
    mode: Mode = Mode.HOST
    runtime: Runtime = Runtime.DOCKER


DEFAULT_ENVIRONMENT = Environment()
"""What a workspace answers by saying nothing, and what every question about
the environment is asked with when there is no file to read it from."""
