"""One build at a time per (branch set, build unit).

A worktree's scratch paths are symlinks keyed by profile, so they carry state:
two `cjdev build compiler` runs at different profiles in one branch set would
repoint each other's links mid-build. Different units share nothing, so the
lock is no wider than that.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePath

from cjdev.errors import PreconditionError

try:
    from fcntl import LOCK_EX, LOCK_NB, LOCK_UN, flock
except ImportError:  # pragma: no cover - Windows has no flock
    flock = None


@contextmanager
def file_lock(path: PurePath) -> Iterator[None]:
    """Refuses rather than waits.

    A build takes forty minutes, so blocking would look exactly like a build
    that has hung; a message naming the other run is something the user can
    act on.
    """
    if flock is None:
        raise PreconditionError(
            "cjdev build needs flock to serialise builds, and this platform "
            "does not have it."
        )
    lock = Path(path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("w", encoding="utf-8") as handle:
        try:
            flock(handle, LOCK_EX | LOCK_NB)
        except OSError as busy:
            raise PreconditionError(
                f"another cjdev build already holds {lock.name}.",
                remedy="wait for it to finish",
            ) from busy
        try:
            yield
        finally:
            flock(handle, LOCK_UN)


@contextmanager
def no_lock(path: PurePath) -> Iterator[None]:  # noqa: ARG001 - the port's shape
    """A dry run creates no files, lock files included."""
    yield
