"""`cjdev env`: the image, and one command with the build's environment.

The point of the third subcommand is that a build's journal line becomes
something a person can run again, so what is asserted here is that the command
`env run` produces is the one a build step would have produced - same
environment, same working directory - and that it is handed the terminal
rather than captured.
"""

from pathlib import Path, PurePath
from typing import final

import pytest

from cjdev.application.manage_environment import ManageEnvironment
from cjdev.application.ports import Command, Completed, Executor, FileSystem
from cjdev.domain.build import Host, Profile
from cjdev.domain.environment import Environment, Mode
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import PreconditionError

ROOT = Path("/ws")
HOST = Host(
    target="linux_x86_64",
    jobs=4,
    path="/usr/bin",
    library_var="LD_LIBRARY_PATH",
    library_path="",
    ccache=None,
)


@final
class FakeExecutor:
    def __init__(self, exit_code: int = 0) -> None:
        self.ran: list[Command] = []
        self._exit_code = exit_code

    def run(self, command: Command, *, check: bool = True) -> Completed:
        self.ran.append(command)
        return Completed(command, self._exit_code, "", "")


@final
class FakeFileSystem:
    def __init__(self) -> None:
        self.made: list[PurePath] = []
        self.written: list[tuple[PurePath, str]] = []

    def mkdir(self, path: PurePath) -> None:
        self.made.append(path)

    def write_text(self, path: PurePath, text: str) -> None:
        self.written.append((path, text))

    def remove(self, path: PurePath) -> None: ...

    def symlink(self, link: PurePath, target: PurePath) -> None: ...

    def copy(self, source: PurePath, into: PurePath) -> None: ...


def fake_build_image(
    executor: Executor, fs: FileSystem, layout: WorkspaceLayout
) -> None:
    """What the composition root binds to a runtime, minus the runtime."""
    fs.mkdir(layout.image_dir)
    fs.write_text(layout.image_dir / "Dockerfile", "FROM scratch\n")
    executor.run(Command(argv=("docker", "build"), cwd=Path(layout.root)))


def fake_remove_image(executor: Executor) -> None:
    executor.run(Command(argv=("docker", "image", "rm"), cwd=ROOT))


def use_case(
    *,
    mode: Mode = Mode.CONTAINER,
    outside: FakeExecutor | None = None,
    inside: FakeExecutor | None = None,
    file_system: FakeFileSystem | None = None,
) -> ManageEnvironment:
    outside = outside or FakeExecutor()
    return ManageEnvironment(
        outside=outside,  # type: ignore[arg-type]
        inside=(inside or outside),  # type: ignore[arg-type]
        file_system=file_system or FakeFileSystem(),  # type: ignore[arg-type]
        host=lambda: HOST,
        environment=Environment(mode),
        build_image=fake_build_image,
        remove_image=fake_remove_image,
        shell=("/bin/bash",),
    )


class TestTheImage:
    def test_the_recipe_is_written_where_the_daemon_will_read_it(self):
        # Arrange
        fs, executor = FakeFileSystem(), FakeExecutor()

        # Act
        use_case(outside=executor, file_system=fs).build(ROOT)

        # Assert
        assert fs.made == [WorkspaceLayout(ROOT).image_dir]
        assert fs.written[0][0] == WorkspaceLayout(ROOT).image_dir / "Dockerfile"
        assert executor.ran[0].argv == ("docker", "build")

    def test_a_host_workspace_has_no_image_to_build(self):
        # Act / Assert
        with pytest.raises(PreconditionError) as refusal:
            use_case(mode=Mode.HOST).build(ROOT)
        assert refusal.value.remedy == 'set mode = "container" in .cjdev/config.toml'

    def test_a_host_workspace_has_no_image_to_remove_either(self):
        # Act / Assert
        with pytest.raises(PreconditionError, match="no image to remove"):
            use_case(mode=Mode.HOST).remove()

    def test_removing_it_is_the_whole_of_the_state_container_mode_leaves(self):
        # Arrange
        executor = FakeExecutor()

        # Act: there is no container to stop - every command runs its own.
        use_case(outside=executor).remove()

        # Assert
        assert executor.ran[0].argv == ("docker", "image", "rm")


class TestRunningOneCommand:
    def test_it_lands_with_the_environment_a_build_step_would_have(self):
        # Arrange
        inside = FakeExecutor()

        # Act
        use_case(inside=inside).run(
            ROOT,
            "main",
            profile=Profile.RELEASE,
            cwd=Path("/ws/main/cangjie_compiler"),
            argv=("cmake", "--version"),
        )

        # Assert: the point is reproducing a journal line, and a step run
        # without the build's environment is a different command.
        command = inside.ran[0]
        assert command.argv == ("cmake", "--version")
        assert command.cwd == Path("/ws/main/cangjie_compiler")
        assert command.env["CANGJIE_HOME"] == "/ws/.cjdev/dist/main/container/release"

    def test_it_is_given_the_terminal_rather_than_captured(self):
        # Arrange
        inside = FakeExecutor()

        # Act
        use_case(inside=inside).run(
            ROOT, "main", profile=Profile.RELEASE, cwd=ROOT, argv=("ls",)
        )

        # Assert: one foreground command is not a worker in a fan-out, so the
        # rule that output is captured and replayed does not reach it.
        assert inside.ran[0].interactive

    def test_no_argv_is_a_shell_in_the_same_environment(self):
        # Arrange
        inside = FakeExecutor()

        # Act
        use_case(inside=inside).run(ROOT, "main", profile=Profile.RELEASE, cwd=ROOT)

        # Assert
        assert inside.ran[0].argv == ("/bin/bash",)

    def test_the_command_s_own_exit_code_comes_back(self):
        # Arrange: a compiler exiting 1 is an answer, not cjdev failing.
        inside = FakeExecutor(exit_code=2)

        # Act
        code = use_case(inside=inside).run(
            ROOT, "main", profile=Profile.RELEASE, cwd=ROOT, argv=("false",)
        )

        # Assert
        assert code == 2

    def test_host_mode_runs_here_with_the_host_tree(self):
        # Arrange
        inside = FakeExecutor()

        # Act
        use_case(mode=Mode.HOST, inside=inside).run(
            ROOT, "main", profile=Profile.DEBUG, cwd=ROOT, argv=("ls",)
        )

        # Assert: the same command on both sides of the port, and the paths
        # say which side it is.
        assert inside.ran[0].env["CANGJIE_HOME"] == "/ws/.cjdev/dist/main/host/debug"
