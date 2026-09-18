"""How a build unit is invoked, and what a build writes into.

The per-unit vocabularies genuinely differ - `-t` is an enum for the compiler
and a free string for cjpm, `cjpm` installs by copying two files into two
directories while the cmake units run their own `install` - so the argv and the
install shape are manifest data.

What is deliberately *not* data is the substitution: four tokens, replaced
literally, with no conditionals. The moment a template needs an `if`, the
manifest has become a programming language and the logic belongs here.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import PurePath, PurePosixPath
from typing import final

from cjdev.errors import ManifestError

PROFILE = "profile"
JOBS = "jobs"
DIST = "dist"
BUILD_DIR = "build_dir"

TOKENS = (PROFILE, JOBS, DIST, BUILD_DIR)
"""Everything a template may say. An unknown token is refused where the file
is read rather than substituted into argv as a literal `{prefix}`, which the
build script would take as a path and fail on much later."""

_TOKEN = re.compile(r"{([^{}]*)}")


@final
@unique
class Profile(Enum):
    """cjdev's own build-type vocabulary, reaching each script as `{profile}`.

    It stops at two because `cjpm` does: its `-t` hard-errors on anything but
    these, while the three cmake units also accept `relwithdebinfo`. A word
    that works for three units out of four is not a vocabulary.
    """

    DEBUG = "debug"
    RELEASE = "release"

    def __str__(self) -> str:
        return self.value


@final
@dataclass(frozen=True)
class RunStep:
    """An argv to run in the unit's directory, tokens still unsubstituted."""

    argv: tuple[str, ...]


@final
@dataclass(frozen=True)
class CopyStep:
    """One file, into one directory.

    `cjpm` needs this: its binary belongs in `tools/bin` and its
    `cangjie-repo.toml` in `tools/config`, and cjpm falls back to an empty
    config *without an error* when the two share a directory. Upstream's own
    `install --prefix` puts both in one place, so a single argv cannot express
    it - and its install is two `shutil.copy` calls, so doing the copies here
    beats running it and moving a file afterwards.
    """

    source: PurePosixPath
    """Relative to the unit's directory."""
    into: str
    """A template, because the destination is under `{dist}`."""


InstallStep = RunStep | CopyStep


@final
@dataclass(frozen=True)
class Host:
    """What the machine a build runs on contributes.

    Passed in rather than read where it is used, so the decision a build makes
    is assertable without a ccache, a PATH or a particular core count.
    """

    target: str
    """`linux_x86_64`: the directory segment upstream names its per-target
    output after."""
    jobs: int
    path: str
    """The `PATH` the SDK's `bin` directories and the ccache shim go in front
    of."""
    library_var: str
    """`LD_LIBRARY_PATH`, or `DYLD_FALLBACK_LIBRARY_PATH` on macOS: the name is
    the platform's, not ours."""
    library_path: str
    ccache: PurePath | None
    """The `ccache` binary, when this machine has one."""


def native_target(system: str, machine: str) -> str:
    """`linux_x86_64`: the segment upstream names a native build's output after.

    One spelling serves both places cjdev needs it - stdx's install directories
    and the SDK's runtime library path - and the arch is canonicalised because
    both sources canonicalise it: `envsetup.sh` rewrites `arm64`, and every
    native cmake toolchain file pins `CMAKE_SYSTEM_PROCESSOR` to `aarch64` or
    `x86_64` rather than taking the host's word for it.
    """
    arch = machine.replace("AMD64", "x86_64").lower().replace("arm64", "aarch64")
    return f"{system.lower()}_{arch}"


def substitute(text: str, values: Mapping[str, str]) -> str:
    return _TOKEN.sub(lambda match: values[match.group(1)], text)


def check_template(text: str, where: str) -> None:
    unknown = sorted(set(_TOKEN.findall(text)) - set(TOKENS))
    if unknown:
        raise ManifestError(
            f"{where} uses unknown token(s) {', '.join(unknown)}. "
            f"Known tokens: {', '.join(TOKENS)}."
        )


def check_scratch(path: PurePosixPath, where: str) -> None:
    """A scratch path is where a symlink gets written, and the symlink gets
    removed, so a name that escapes the worktree is the whole risk here."""
    parts = path.parts
    if not parts or path.is_absolute() or ".." in parts or "." in parts:
        raise ManifestError(
            f"{where} scratch path must be relative and free of '.' and "
            f"'..', got {str(path)!r}."
        )
