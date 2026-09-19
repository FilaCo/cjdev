"""Container mode, and the argv it produces.

Two kinds of test here. Everything that builds an argv, hashes a Dockerfile or
reads what a runtime printed is pure and runs anywhere: that is most of the
module, and it is pure on purpose. What genuinely needs a daemon is marked
`container` and skips without one, and it exercises the contract rather than
cjdev's own image - whether the mount really lands at the same path and what
the build writes really belongs to the caller are the two things a fake can
never answer, and a five megabyte image answers them in seconds.
"""

import os
from pathlib import Path, PurePath
from typing import Any, final

import pytest

from cjdev.application.ports import Command, Completed
from cjdev.domain.environment import Runtime
from cjdev.errors import CommandError, PreconditionError
from cjdev.infra.container import (
    CCACHE_LABEL,
    NO_VALUE,
    ContainerSpec,
    bundled_dockerfile,
    containerise,
    detect_container_host,
    image_command,
    image_tag,
    remove_image_command,
    require_runtime,
)
from cjdev.infra.executor import build_executor
from cjdev.infra.executor.container import ContainerExecutor
from cjdev.infra.executor.host import HostExecutor

ROOT = PurePath("/ws")
TAG = "cjdev-build:0123456789ab"

PROBE_IMAGE = "alpine:3.20"
"""Small enough to pull in seconds, and it is the runtime's behaviour under
test rather than anything of ours."""


def spec(runtime: Runtime = Runtime.DOCKER, **overrides: object) -> ContainerSpec:
    fields: dict[str, Any] = {
        "runtime": runtime,
        "tag": TAG,
        "root": ROOT,
        "home": ROOT / ".cjdev" / "cache" / "home",
        "uid": 501,
        "gid": 20,
        "selinux": False,
    }
    fields.update(overrides)
    return ContainerSpec(**fields)


def a_command(**overrides: object) -> Command:
    fields: dict[str, Any] = {
        "argv": ("python3", "build.py", "build"),
        "cwd": Path("/ws/main/cangjie_compiler"),
        "env": {"CANGJIE_HOME": "/ws/.cjdev/dist/main/container/release"},
    }
    fields.update(overrides)
    return Command(**fields)


@final
class FakeExecutor:
    """Answers with what a runtime would have printed."""

    def __init__(self, *answers: str | CommandError) -> None:
        self.ran: list[Command] = []
        self._answers = list(answers)

    def run(self, command: Command, *, check: bool = True) -> Completed:
        self.ran.append(command)
        answer = self._answers.pop(0) if self._answers else ""
        if isinstance(answer, CommandError):
            raise answer
        return Completed(command, 0, answer, "")


class TestTheTag:
    def test_it_is_the_dockerfile_that_names_the_image(self):
        # Arrange / Act
        tag = image_tag("FROM ubuntu:22.04\n")

        # Assert
        assert tag.startswith("cjdev-build:")
        assert len(tag.split(":")[1]) == 12

    def test_an_edit_cannot_be_shadowed_by_the_image_before_it(self):
        # Arrange / Act / Assert
        assert image_tag("FROM ubuntu:22.04\n") != image_tag("FROM ubuntu:24.04\n")

    def test_the_bundled_recipe_is_reachable_from_an_installed_wheel(self):
        # Arrange / Act: through importlib.resources, not the working tree,
        # or a packaging regression only shows up for users.
        text = bundled_dockerfile()

        # Assert
        assert text.startswith("#")
        assert "FROM ubuntu:22.04" in text

    def test_the_image_declares_the_label_cjdev_reads_back(self):
        # Arrange / Act / Assert: the two halves of one contract, and nothing
        # else would catch them drifting apart until a build had no ccache.
        assert f'LABEL {CCACHE_LABEL}="' in bundled_dockerfile()


class TestTheArgv:
    def test_the_command_runs_inside_at_the_path_it_was_given(self):
        # Arrange / Act
        argv = containerise(a_command(), spec()).argv

        # Assert: one mount, identity, and the image last before the command.
        assert argv[:5] == ("docker", "run", "--rm", "--init", "--volume")
        assert argv[5] == "/ws:/ws"
        assert "--workdir" in argv
        assert argv[argv.index("--workdir") + 1] == "/ws/main/cangjie_compiler"
        assert argv[-4:] == (TAG, "python3", "build.py", "build")

    def test_the_environment_moves_onto_the_argv_and_off_the_command(self):
        # Arrange / Act
        command = containerise(a_command(), spec())

        # Assert: left on the command it would be the *client's* environment,
        # and a container's PATH exported here loses us the runtime binary.
        assert command.env == {}
        assert "-e" in command.argv
        assert "CANGJIE_HOME=/ws/.cjdev/dist/main/container/release" in command.argv
        assert "HOME=/ws/.cjdev/cache/home" in command.argv

    def test_docker_maps_the_caller_and_podman_must_not(self):
        # Arrange / Act
        docker = containerise(a_command(), spec(Runtime.DOCKER)).argv
        podman = containerise(a_command(), spec(Runtime.PODMAN)).argv

        # Assert: rootless podman already maps the caller onto root inside, so
        # --user is what breaks it there.
        assert "--user" in docker and "501:20" in docker
        assert "--userns=keep-id" in podman
        assert "--user" not in podman
        assert not any(arg.startswith("--userns") for arg in docker)

    def test_selinux_relabels_the_mount_and_only_then(self):
        # Arrange / Act / Assert
        assert containerise(a_command(), spec(selinux=True)).argv[5] == "/ws:/ws:z"
        assert containerise(a_command(), spec()).argv[5] == "/ws:/ws"

    def test_an_interactive_command_is_given_the_terminal(self):
        # Arrange / Act
        argv = containerise(a_command(interactive=True), spec()).argv

        # Assert
        assert "--interactive" in argv and "--tty" in argv
        assert "--tty" not in containerise(a_command(), spec()).argv

    def test_the_build_context_is_not_the_workspace(self):
        # Arrange / Act
        argv = image_command(spec(), ROOT / ".cjdev" / "cache" / "image").argv

        # Assert: the workspace is gigabytes the image copies none of.
        assert argv == (
            "docker",
            "build",
            "--tag",
            TAG,
            "/ws/.cjdev/cache/image",
        )

    def test_the_image_is_removed_by_the_tag_it_was_built_under(self):
        # Arrange / Act / Assert
        assert remove_image_command(spec()).argv == ("docker", "image", "rm", TAG)


class TestWhatTheEnvironmentAnswers:
    def test_the_daemon_and_the_image_are_both_asked_from_out_here(self):
        # Arrange
        executor = FakeExecutor(
            "linux aarch64 8",
            "/usr/bin/ccache\nPATH=/usr/local/bin:/usr/bin\nHOME=/root\n",
        )

        # Act
        host = detect_container_host(executor, spec())

        # Assert
        assert host.target == "linux_aarch64"
        assert host.jobs == 8
        assert host.path == "/usr/local/bin:/usr/bin"
        assert host.ccache == PurePath("/usr/bin/ccache")
        assert host.library_var == "LD_LIBRARY_PATH"
        # Neither read needs a container, so a dry run may make them for real.
        assert [command.mutates for command in executor.ran] == [False, False]

    def test_podman_spells_the_architecture_its_own_way(self):
        # Arrange: docker says aarch64, podman says arm64, and the SDK's
        # directory names take neither on trust.
        executor = FakeExecutor("linux arm64 4", f"{NO_VALUE}\nPATH=/usr/bin\n")

        # Act
        host = detect_container_host(executor, spec(Runtime.PODMAN))

        # Assert
        assert host.target == "linux_aarch64"
        assert host.ccache is None

    def test_an_image_without_ccache_is_a_build_without_a_shim(self):
        # Arrange
        executor = FakeExecutor("linux x86_64 2", "\nPATH=/usr/bin\n")

        # Act / Assert
        assert detect_container_host(executor, spec()).ccache is None

    def test_a_daemon_that_does_not_answer_is_a_precondition(self):
        # Arrange
        executor = FakeExecutor(
            CommandError(
                argv=("docker", "info"),
                cwd="/ws",
                exit_code=1,
                output="Cannot connect to the Docker daemon",
            )
        )

        # Act / Assert: the world is not ready, and the fix is not in the argv.
        with pytest.raises(PreconditionError) as refusal:
            detect_container_host(executor, spec())
        assert refusal.value.remedy == "start docker and try again"

    def test_a_missing_image_names_the_command_that_builds_it(self):
        # Arrange
        executor = FakeExecutor(
            "linux x86_64 2",
            CommandError(
                argv=("docker", "image", "inspect"),
                cwd="/ws",
                exit_code=1,
                output="No such image",
            ),
        )

        # Act / Assert
        with pytest.raises(PreconditionError) as refusal:
            detect_container_host(executor, spec())
        assert refusal.value.remedy == "cjdev env build"

    def test_nonsense_from_info_is_refused_rather_than_parsed(self):
        # Arrange
        executor = FakeExecutor("some other thing entirely")

        # Act / Assert
        with pytest.raises(PreconditionError, match="not an OS"):
            detect_container_host(executor, spec())

    def test_a_runtime_that_is_not_installed_is_its_own_failure(self, monkeypatch):
        # Arrange: three preflight failures with three different fixes, and
        # this is the one there is no binary to ask about.
        monkeypatch.setattr("cjdev.infra.container.shutil.which", lambda _: None)

        # Act / Assert
        with pytest.raises(PreconditionError, match="not installed"):
            require_runtime(Runtime.DOCKER)


class TestTheExecutor:
    def test_a_dry_run_prints_what_would_run_and_starts_nothing(self):
        # Arrange: the executor sits above the dry run, so what gets printed
        # is the run, not the argv nobody typed. Nothing below it is reachable
        # without a daemon, which is the other half of the assertion.
        printed: list[str] = []
        executor = ContainerExecutor(
            build_executor(dry_run=True, emit=printed.append), spec()
        )

        # Act
        executor.run(a_command())

        # Assert
        assert "docker run --rm --init" in printed[0]
        assert "--volume /ws:/ws" in printed[0]
        assert f"{TAG} python3 build.py build" in printed[0]

    def test_everything_below_it_sees_the_argv_that_will_really_run(self):
        # Arrange: the log, `-v` and `--dry-run` all sit under it, and an
        # inner argv with no mount and no uid on it answers nobody's question.
        inner = FakeExecutor()

        # Act
        ContainerExecutor(inner, spec()).run(a_command())

        # Assert
        assert inner.ran[0].argv[0] == "docker"
        assert inner.ran[0].argv[1] == "run"
        assert "python3" in inner.ran[0].argv


@pytest.mark.container
class TestAgainstARealRuntime:
    """What a fake cannot answer: whether the mount lands where FR-7 says and
    whether what the build writes belongs to the caller."""

    def test_the_workspace_is_at_the_same_absolute_path_inside(
        self, container_runtime: str, tmp_path: Path
    ):
        # Arrange
        (tmp_path / "marker").write_text("here", encoding="utf-8")
        command = containerise(
            Command(argv=("cat", "marker"), cwd=tmp_path),
            spec(
                Runtime(container_runtime),
                tag=PROBE_IMAGE,
                root=tmp_path,
                home=tmp_path,
            ),
        )

        # Act
        result = HostExecutor().run(command)

        # Assert: the scratch symlinks are relative and clangd reads absolute
        # paths, and both need this to be true.
        assert result.stdout.strip() == "here"

    def test_what_it_writes_belongs_to_the_caller(
        self, container_runtime: str, tmp_path: Path
    ):
        # Arrange
        command = containerise(
            Command(argv=("touch", "written"), cwd=tmp_path),
            spec(
                Runtime(container_runtime),
                tag=PROBE_IMAGE,
                root=tmp_path,
                home=tmp_path,
                uid=os.getuid(),
                gid=os.getgid(),
            ),
        )

        # Act
        HostExecutor().run(command)

        # Assert: rootful docker would leave this owned by root.
        assert (tmp_path / "written").stat().st_uid == os.getuid()
