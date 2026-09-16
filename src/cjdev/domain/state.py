"""What a workspace currently holds: branch sets, checkouts and their git state.

The shape `status` reports. Every value here is read back from git rather than
kept in a file of our own, so these types are a
*snapshot* - two of them taken a second apart may legitimately disagree, and
nothing may cache one across a mutating command.

Pure, like the rest of `domain/`: `PurePath` again, so grouping worktrees into
branch sets can be asserted on without a repository to read them from.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import PurePath
from typing import final


@final
@dataclass(frozen=True)
class Tracking:
    """How far a branch has drifted from one remote's copy of it.

    Absent rather than zeroed when the remote has no such branch: "never
    pushed" and "in sync" are different answers, and a pair of zeros cannot
    tell them apart.
    """

    remote: str
    ahead: int
    behind: int


@final
@dataclass(frozen=True)
class Checkout:
    """One project's worktree inside one branch set."""

    project: str
    path: PurePath
    branch: str | None
    """None when the worktree is detached: a project enrolled into the branch
    set lazily still sits on the pinned base ref."""
    head: str
    """The full SHA. Abbreviating is the renderer's business, so that `--json`
    stays useful to something that wants to look the commit up."""
    dirty: bool
    tracking: tuple[Tracking, ...]


@final
@dataclass(frozen=True)
class BranchSet:
    name: str
    directory: PurePath
    checkouts: tuple[Checkout, ...]
    """In manifest order, never in the order git happened to report them."""


@final
@dataclass(frozen=True)
class StaleRegistration:
    """One registration git keeps for a worktree it can no longer enter.

    Not an error and not a checkout: the project read fine, nothing is
    corrupted, and a row in a branch-set table would describe a worktree git
    refuses to query. Named with its fact and its remedy because the report
    is otherwise one the reader cannot act on: git refuses both `worktree
    add` on that path and every query that would enter it.
    """

    path: PurePath
    fact: str
    """What is wrong, as a sentence that holds for this registration alone.

    `prunable` - the flag git sets - does not by itself say what is wrong:
    it fires as readily for a directory that is gone as for a checkout that
    is still in place under a broken registration, and the remedy differs
    (`repair` reconnects the latter, a prune under it would destroy a live
    checkout). The fact says which case this is."""
    remedy: str
    """The command that fixes it, runnable as printed - the full
    `git -C <store>` form (why, see `_stale_registration`)."""


@final
@dataclass(frozen=True)
class Store:
    project: str
    provisioned: bool
    error: str | None = None
    """Why this project could not be read. Set on one project rather than
    raised, because five readable projects are still worth printing."""
    stale: tuple[StaleRegistration, ...] = ()
    """This store's stale registrations; what they are and why they are
    reported beside the checkouts, see `StaleRegistration`."""


@final
@dataclass(frozen=True)
class StoreReading:
    """What one object store yielded: its live checkouts, and the stale
    registrations it still holds.

    The shape `read_store` returns, one store per fan-out unit. Two tuples
    rather than one list of variants because the report does different things
    with them: a checkout is described, a stale registration is named with
    its fact and remedy and never entered again.
    """

    checkouts: tuple[Checkout, ...]
    stale: tuple[StaleRegistration, ...]


@final
@dataclass(frozen=True)
class WorkspaceStatus:
    root: PurePath
    active: str | None
    stores: tuple[Store, ...]
    branch_sets: tuple[BranchSet, ...]


def branch_sets_of(
    root: PurePath, checkouts: Iterable[Checkout]
) -> tuple[BranchSet, ...]:
    """Group the worktrees git reported into the branch sets they belong to.

    Grouping by directory rather than by branch name is what tolerates lazy
    enrolment: a detached project has no branch to group on, but it does sit
    next to its siblings.
    """
    grouped: dict[PurePath, list[Checkout]] = {}
    for checkout in checkouts:
        directory = checkout.path.parent
        # git reported it, but a worktree that is not one directory below the
        # root is not one cjdev laid out - it was linked from somewhere else,
        # and this report describes the workspace, not everything git knows.
        if directory.parent != root:
            continue
        grouped.setdefault(directory, []).append(checkout)

    return tuple(
        BranchSet(
            name=_name_of(directory, members),
            directory=directory,
            checkouts=tuple(members),
        )
        for directory, members in sorted(grouped.items())
    )


def active_branch_set(
    root: PurePath, cwd: PurePath, branch_sets: Sequence[BranchSet]
) -> str | None:
    """The branch set the user is standing in, or None if they are elsewhere.

    Matched on the directory rather than on the name, because flattening is
    one-way: turning `fix/ice` back into a directory to compare would have to
    guess, and refusing a colliding branch-set name is what makes the directory
    an unambiguous key in the first place.
    """
    for directory in (cwd, *cwd.parents):
        if directory == root:
            return None
        if directory.parent == root:
            return next((s.name for s in branch_sets if s.directory == directory), None)
    return None


def _name_of(directory: PurePath, checkouts: Sequence[Checkout]) -> str:
    """The branch checked out in it, not the directory holding it.

    A branch set whose every project is still detached has no branch to read,
    and falls back to the flattened label on disk - lossy, and the best that
    exists until the first project is enrolled.
    """
    return next((c.branch for c in checkouts if c.branch is not None), directory.name)
