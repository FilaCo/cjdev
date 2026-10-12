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
@unique
class ImagePolicy(Enum):
    """What a build does when the image for this cjdev's Dockerfile is missing.

    Building it is the default because nothing about it is the caller's to
    choose: the recipe ships with cjdev and the tag is its hash. Refusing is
    for a run that must not change anything outside the workspace, CI first.
    """

    BUILD = "build"
    REFUSE = "refuse"

    def __str__(self) -> str:
        return self.value


@final
@dataclass(frozen=True)
class Environment:
    mode: Mode = Mode.HOST
    runtime: Runtime = Runtime.DOCKER
    image: ImagePolicy = ImagePolicy.BUILD


DEFAULT_ENVIRONMENT = Environment()
"""What a workspace answers by saying nothing, and what every question about
the environment is asked with when there is no file to read it from."""
