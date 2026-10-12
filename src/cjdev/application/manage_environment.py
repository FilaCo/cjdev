"""`cjdev env`: the image a containerised build needs, and one command inside it.

The third subcommand is the reason the other two are not enough. A build
records the full argv of everything it ran, mount and uid and every `-e`
included, and `env run` is what makes that line reproducible by hand: the same
environment, the same working directory, the same image, one command of the
caller's choosing. Reassembling twenty flags from a log is not debugging.

It works in host mode too, running on the host with the environment a build
would have given it. That is not a courtesy - it is the one command that
behaves identically on both sides of the port, which is what makes the port
worth having.
"""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import final

from cjdev.application.build_units import HostProvider, build_environment
from cjdev.application.ports import Command, Executor, FileSystem
from cjdev.application.runner import Runner, RunObserver, Work
from cjdev.domain.build import Profile
from cjdev.domain.environment import Environment, ImagePolicy, Mode
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import PreconditionError

BuildImage = Callable[[Executor, FileSystem, WorkspaceLayout], None]
RemoveImage = Callable[[Executor], None]
ImagePresent = Callable[[Executor], bool]
"""Bound to a runtime by the composition root, the way `init` receives its
`provision` and `remove`. Nothing here knows what a Dockerfile is."""

IMAGE = "image"
"""The row a build shows while it builds its image first."""


@final
class ManageEnvironment:
    def __init__(
        self,
        outside: Executor,
        inside: Executor,
        file_system: FileSystem,
        host: HostProvider,
        environment: Environment,
        build_image: BuildImage,
        remove_image: RemoveImage,
        image_present: ImagePresent,
        shell: Sequence[str],
    ) -> None:
        self._outside = outside
        """Where the image is built: the runtime CLI runs on this machine, and
        wrapping it in the runtime would be a container building an image."""
        self._inside = inside
        """Where a command lands. The same executor as `outside` in host mode,
        which is what makes `env run` one command rather than two."""
        self._fs = file_system
        self._host = host
        self._environment = environment
        self._build_image = build_image
        self._remove_image = remove_image
        self._image_present = image_present
        self._shell = tuple(shell)

    def build(self, root: Path) -> None:
        self._require_container("build")
        self._build_image(self._outside, self._fs, WorkspaceLayout(root))

    def image_missing(self) -> bool:
        """Whether a build has to build the image before it can plan.

        A read, so a dry run answers it for real. Under `refuse` the absence
        is the answer: the caller wanted it named, not paid for.
        """
        if self._environment.mode is Mode.HOST:
            return False
        if self._image_present(self._outside):
            return False
        if self._environment.image is ImagePolicy.REFUSE:
            raise PreconditionError(
                'the image is not built, and image = "refuse" in '
                ".cjdev/config.toml keeps a build from building it.",
                remedy="cjdev env build",
            )
        return True

    def provision(self, root: Path, *, observer: RunObserver | None = None) -> None:
        """`build`, as a tracked row: minutes of image are shown being spent,
        which is what answers the case for refusing to spend them."""
        report = Runner(1).run(
            [Work(key=IMAGE, label=IMAGE, action=lambda: self.build(root))],
            observer=observer,
        )
        if report.interrupted:
            raise KeyboardInterrupt
        error = report.results[0].error
        if error is not None:
            raise error

    def remove(self) -> None:
        """No root: the image is the machine's, not the workspace's, and the
        tag it is removed by came from the Dockerfile rather than from here."""
        self._require_container("remove")
        self._remove_image(self._outside)

    def run(
        self,
        root: Path,
        branch_set: str,
        *,
        profile: Profile,
        cwd: Path,
        argv: Sequence[str] = (),
    ) -> int:
        """One command, with the terminal, and its exit code back.

        Not checked: the caller asked to run something and the something
        failing is an answer, not a cjdev failure. A shell exits 130 on Ctrl-D
        as readily as a compiler exits 1, and neither is this command going
        wrong.
        """
        layout = WorkspaceLayout(root)
        where = self._environment.mode.value
        command = Command(
            argv=tuple(argv) or self._shell,
            cwd=cwd,
            env=build_environment(layout, branch_set, where, profile, self._host()),
            interactive=True,
            what="running" if argv else "a shell",
        )
        return self._inside.run(command, check=False).exit_code

    def _require_container(self, verb: str) -> None:
        if self._environment.mode is Mode.HOST:
            raise PreconditionError(
                f"this workspace builds on the host, so there is no image to {verb}.",
                remedy='set mode = "container" in .cjdev/config.toml',
            )
