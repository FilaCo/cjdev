"""Turning a command into the same command, run inside the image."""

from typing import final

from cjdev.application.ports import Command, Completed, Executor
from cjdev.infra.container import ContainerSpec, containerise


@final
class ContainerExecutor:
    """Outermost of the stack, not innermost.

    Everything below it - dry run, the step label, `-v`, the workspace log -
    then sees the argv that will really run. "What did that actually run?" is
    the only question the log exists to answer, and an inner argv nobody typed,
    with no mount and no uid on it, is not an answer.

    It runs nothing itself: the rewritten command goes back down the same stack
    and the host executor at the bottom runs the runtime binary.
    """

    def __init__(self, inner: Executor, spec: ContainerSpec) -> None:
        self._inner = inner
        self._spec = spec

    def run(self, command: Command, *, check: bool = True) -> Completed:
        return self._inner.run(containerise(command, self._spec), check=check)
