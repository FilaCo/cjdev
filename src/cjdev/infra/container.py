"""Running a build inside a container, and the two ways the runtimes differ.

One `run --rm` per command rather than a long-lived container. The unit of work
is a build unit, tens of minutes of compiling, so the couple of hundred
milliseconds a container costs to create is noise - and what it buys is that
there is no name to derive, no staleness to check, nothing to reclaim, and a
cancellation that works: `docker run` proxies signals to pid 1, `--init` gives
it something that forwards them, and `--rm` reaps what is left.

The image describes itself. Nothing probes it from the inside: `info` answers
what the daemon will run the build on and `image inspect` answers what is in
the image, both from the host, both read-only, so a dry run may ask them and
neither needs a container to exist.

The deltas per runtime are data here, the way `infra/git.py` holds argv for
git. They are not one argv with the program name swapped: rootful docker runs
as root and needs `--user` for what it writes to belong to the caller, while
rootless podman already maps the caller onto the container's root, so `--user`
is what breaks it there.
"""

import hashlib
import os
import shutil
import sys
from dataclasses import dataclass, replace
from importlib.resources import files
from pathlib import Path, PurePath
from typing import final

from cjdev.application.ports import Command, Completed, Executor, FileSystem
from cjdev.domain.build import Host, native_target
from cjdev.domain.environment import Runtime
from cjdev.domain.layout import WorkspaceLayout
from cjdev.errors import CommandError, PreconditionError

DOCKERFILE = "Dockerfile"
IMAGE_NAME = "cjdev-build"
TAG_LENGTH = 12
"""Enough of the digest to name an image, and short enough to read in a
`docker ps` line. Collisions do not matter here: the tag names one recipe in
one workspace, not a content store."""

CCACHE_LABEL = "dev.cjdev.ccache"
"""Where the image keeps `ccache`, declared by the image rather than guessed
from a list of likely paths."""

SELINUX_MARKER = PurePath("/sys/fs/selinux")

INFO_FORMAT = {
    Runtime.DOCKER: "{{.OSType}} {{.Architecture}} {{.NCPU}}",
    Runtime.PODMAN: "{{.Host.OS}} {{.Host.Arch}} {{.Host.CPUs}}",
}
"""Three answers in one read: what the daemon runs, on what, and with how many
CPUs. The spellings differ because the two runtimes report their own structs,
and so do the architectures: docker prints the kernel's (`x86_64`, `aarch64`),
podman prints Go's (`amd64`, `arm64`), which `native_target` folds together."""

INSPECT_FORMAT = (
    f'{{{{index .Config.Labels "{CCACHE_LABEL}"}}}}'
    "{{println}}{{range .Config.Env}}{{println .}}{{end}}"
)
"""The ccache path on the first line, then the image's environment. Parsed
here rather than filtered in the template, because the template functions the
two runtimes offer are not the same set."""

NO_VALUE = "<no value>"
"""What a Go template prints for a label the image does not carry."""


@final
@dataclass(frozen=True)
class ContainerSpec:
    """Everything a command needs to become a run of that command inside.

    Frozen and built once per invocation, so that the argv a build produces is
    a pure function of it - which is what makes it assertable without a daemon.
    """

    runtime: Runtime
    tag: str
    root: PurePath
    """The workspace root, mounted at the same absolute path inside. Everything
    cjdev owns is under it by construction, and the scratch symlinks are
    relative, so one mount is the whole workspace on both sides."""
    home: PurePath
    """`HOME` inside. Under the mount, because the image has no passwd entry
    for the uid it is told to run as and an unwritable home breaks anything
    that caches."""
    uid: int
    gid: int
    selinux: bool
    tty: bool
    """Whether the caller has a terminal to attach.

    A property of the process rather than of the command: `--tty` asked for
    when stdin is a pipe is refused outright by the runtime, and the command
    most worth piping is the one `env run` exists for - reproducing a step the
    journal recorded. `--interactive` is unconditional, because stdin being
    forwarded is what makes a pipe work at all.
    """

    @property
    def program(self) -> str:
        return self.runtime.value

    @property
    def mount(self) -> str:
        """`:z` relabels the volume for SELinux, and is meaningless without
        it - a mount option no kernel is enforcing is noise in every argv."""
        return f"{self.root}:{self.root}{':z' if self.selinux else ''}"

    @property
    def ownership(self) -> tuple[str, ...]:
        if self.runtime is Runtime.PODMAN:
            # Rootless podman maps the caller onto the container's root
            # already, so `--user` is what breaks it; `keep-id` is what lines a
            # non-root user inside up with the caller outside.
            return ("--userns=keep-id",)
        return ("--user", f"{self.uid}:{self.gid}")


def image_tag(dockerfile: str) -> str:
    """`cjdev-build:<hash12>`, over the Dockerfile's own bytes.

    The recipe names the image, so an edit to the file cannot be shadowed by a
    stale image built from the one before it, and "is it built" is a question
    about a tag rather than about a date.
    """
    digest = hashlib.sha256(dockerfile.encode("utf-8")).hexdigest()
    return f"{IMAGE_NAME}:{digest[:TAG_LENGTH]}"


def bundled_dockerfile() -> str:
    """The image recipe that ships in the wheel.

    Reached through `importlib.resources` for the bundled manifest's reason: it
    has to be found in an installed wheel, not only in a source checkout.
    """
    resource = files("cjdev.infra") / "data" / DOCKERFILE
    return resource.read_text(encoding="utf-8")


def selinux_enforcing(marker: PurePath = SELINUX_MARKER) -> bool:
    return Path(marker).is_dir()


def build_spec(
    runtime: Runtime, *, root: PurePath, home: PurePath, tag: str
) -> ContainerSpec:
    require_runtime(runtime)
    return ContainerSpec(
        runtime=runtime,
        tag=tag,
        root=root,
        home=home,
        uid=os.getuid(),
        gid=os.getgid(),
        selinux=selinux_enforcing(),
        tty=sys.stdin.isatty(),
    )


def require_runtime(runtime: Runtime) -> None:
    """The first of the three preflight failures, and the only one that is a
    host read rather than a command: there is nothing to ask when there is no
    binary to ask it with."""
    if shutil.which(runtime.value) is None:
        raise PreconditionError(
            f"{runtime.value} is not installed, and this workspace builds in a "
            f"container.",
            remedy=f'install {runtime.value}, or set mode = "host" in '
            f".cjdev/config.toml",
        )


def image_command(spec: ContainerSpec, context: PurePath) -> Command:
    """Build the image from a context holding the Dockerfile and nothing else.

    The workspace is not the context: it is gigabytes of fetched sources, and
    sending it to the daemon to build an image that copies none of it is the
    slowest possible way to do nothing.
    """
    return Command(
        argv=(spec.program, "build", "--tag", spec.tag, str(context)),
        cwd=Path(context),
        what=f"building {spec.tag}",
    )


def remove_image_command(spec: ContainerSpec) -> Command:
    return Command(
        argv=(spec.program, "image", "rm", spec.tag),
        cwd=Path(spec.root),
        what=f"removing {spec.tag}",
    )


def provision_image(
    executor: Executor,
    file_system: FileSystem,
    layout: WorkspaceLayout,
    *,
    spec: ContainerSpec,
    dockerfile: str,
) -> None:
    """Write the recipe where the daemon can read it, then build it.

    The Dockerfile is written out rather than piped in, so that the context is
    a directory holding exactly it, and so that the file the image was built
    from is there to read afterwards.
    """
    file_system.mkdir(layout.image_dir)
    file_system.write_text(layout.image_dir / DOCKERFILE, dockerfile)
    executor.run(image_command(spec, layout.image_dir))


def remove_image(executor: Executor, *, spec: ContainerSpec) -> None:
    executor.run(remove_image_command(spec))


def containerise(command: Command, spec: ContainerSpec) -> Command:
    """The same command, run inside the image, at the same paths.

    The environment moves onto the argv as `-e` flags and is cleared from the
    command, because what is left is the environment of the *client*: a
    container's `PATH` exported to the host process would leave it unable to
    find the runtime binary it is about to run.
    """
    return replace(
        command,
        argv=(
            spec.program,
            "run",
            "--rm",
            # tini as pid 1: it reaps what the build leaves behind, and it
            # forwards the signal the client proxies in when a build is
            # interrupted.
            "--init",
            *(
                ()
                if not command.interactive
                else ("--interactive", "--tty")
                if spec.tty
                else ("--interactive",)
            ),
            "--volume",
            spec.mount,
            "--workdir",
            str(command.cwd),
            *spec.ownership,
            *_env_flags({**dict(command.env), "HOME": str(spec.home)}),
            spec.tag,
            *command.argv,
        ),
        env={},
    )


def _env_flags(env: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        flag for name, value in env.items() for flag in ("-e", f"{name}={value}")
    )


def detect_container_host(executor: Executor, spec: ContainerSpec) -> Host:
    """What the environment contributes, asked of the daemon and the image.

    Both reads are host-side and read-only, so a dry run makes them for real
    and plans from the truth. The daemon answers what it will run the build on;
    the image answers what is in it. Neither needs a container, which is why
    there is nothing to cache and nothing to invalidate: the CPU count is a
    property of the run, not of the image, and a cache keyed by the tag would
    hand back yesterday's answer after the daemon was given more cores.
    """
    system, machine, cpus = _daemon(executor, spec)
    path, ccache = _image(executor, spec)
    return Host(
        target=native_target(system, machine),
        jobs=cpus,
        path=path,
        # A Linux image, and nothing else is buildable: the fallback variable
        # macOS needs is a property of the caller's machine, not of this one.
        library_var="LD_LIBRARY_PATH",
        library_path="",
        ccache=ccache,
    )


def _daemon(executor: Executor, spec: ContainerSpec) -> tuple[str, str, int]:
    result = _read(
        executor,
        Command(
            argv=(spec.program, "info", "--format", INFO_FORMAT[spec.runtime]),
            cwd=Path(spec.root),
            mutates=False,
            what=f"asking {spec.program}",
        ),
        # A binary that is present and a daemon that answers are different
        # failures with different fixes, which is why the missing binary is
        # refused before this ever runs.
        remedy=f"start {spec.program} and try again",
    )
    fields = result.stdout.split()
    if len(fields) != 3 or not fields[2].isdigit():
        raise PreconditionError(
            f"{spec.program} info answered {result.stdout.strip()!r}, which is "
            f"not an OS, an architecture and a CPU count."
        )
    return fields[0], fields[1], int(fields[2])


def _image(executor: Executor, spec: ContainerSpec) -> tuple[str, PurePath | None]:
    result = _read(
        executor,
        Command(
            argv=(
                spec.program,
                "image",
                "inspect",
                "--format",
                INSPECT_FORMAT,
                spec.tag,
            ),
            cwd=Path(spec.root),
            mutates=False,
            what=f"inspecting {spec.tag}",
        ),
        remedy="cjdev env build",
    )
    lines = result.stdout.splitlines()
    ccache = lines[0].strip() if lines else ""
    path = next(
        (line[len("PATH=") :] for line in lines[1:] if line.startswith("PATH=")), ""
    )
    return path, None if ccache in ("", NO_VALUE) else PurePath(ccache)


def _read(executor: Executor, command: Command, *, remedy: str) -> Completed:
    """A read of the runtime, whose failure is a precondition rather than a
    command that went wrong: the world is not ready, and the output of `info`
    is not something the caller can act on."""
    try:
        return executor.run(command)
    except CommandError as failure:
        raise PreconditionError(
            f"{' '.join(command.argv[:3])} failed: {failure.output.strip()}",
            remedy=remedy,
        ) from failure
