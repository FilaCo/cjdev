"""Driving the `git` CLI: building argv, and reading back what it prints.

Not a port. The commitment to the real `git` binary is made once, and that
binary is reached through `Executor`; a second abstraction over the same
subprocess would have no second implementation to justify it. Tests point this
at a real repository in a `tmp_path`, which is fast enough not to need a fake.
"""

from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import final

from cjdev.application.new_branch_set import Action, Enrolment, Held, Probe
from cjdev.application.ports import Command, Executor, FileSystem
from cjdev.domain.manifest import Project
from cjdev.domain.state import Checkout, StaleRegistration, StoreReading, Tracking
from cjdev.errors import PreconditionError

UPSTREAM = "upstream"
"""The canonical repository. Read-only: `cjdev` fetches it and never pushes
to it."""

ORIGIN = "origin"
"""The user's fork, and the only place a fork URL is ever stored - git needs
it here to push at all, so a copy in the workspace config would be a second
source of truth to keep in sync."""

REMOTES = (UPSTREAM, ORIGIN)
"""The two remotes drift is reported against, in the order they are shown."""


@final
@dataclass(frozen=True)
class Linked:
    """One `git worktree list --porcelain` block that is a real checkout."""

    path: str
    head: str
    branch: str | None
    prunable: str | None = None
    """Why git has stopped treating this as a checkout, in git's own words.

    The reason is kept rather than reduced to a flag because it is the only
    thing that distinguishes the ways a registration breaks, and the remedy
    differs by case. None while git still treats the worktree as a checkout.
    Note that `prunable` does not mean the directory is gone: git sets it as
    readily for a checkout whose `.git` file was clobbered while the
    directory - the work in it and all - is still there."""
    locked: bool = False
    """Explicitly locked. How that bears on `prunable`, and why `_dead`
    needs more than `prunable`, see `_dead`."""


@final
class Git:
    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    def init_bare(self, store: Path) -> None:
        self._run(
            ("init", "--bare", "--quiet", store.name),
            cwd=store.parent,
            what="creating the object store",
        )

    def add_remote(self, store: Path, name: str, url: str) -> None:
        self._run(("remote", "add", name, url), cwd=store, what=f"wiring up {name}")

    def remotes(self, store: Path) -> tuple[str, ...]:
        result = self._run(("remote",), cwd=store, mutates=False)
        return tuple(line.strip() for line in result.splitlines() if line.strip())

    def linked_worktrees(self, store: Path) -> tuple[Linked, ...]:
        """The worktrees linked to this store, excluding the store itself.

        `git worktree list` reports a bare repository as an entry of its own,
        marked `bare`; that entry is the store, not a checkout, so it is
        dropped here rather than by every caller.
        """
        blocks = self._run(
            ("worktree", "list", "--porcelain"),
            cwd=store,
            mutates=False,
            what="listing worktrees",
        ).split("\n\n")
        linked = []
        for block in blocks:
            lines = block.splitlines()
            if "bare" in lines:
                continue
            # Every line is `key value` except the flag lines (`bare`,
            # `detached`), which are a bare key and land here with an empty
            # value - which is what makes a missing `branch` the detached case.
            fields = dict(line.partition(" ")[::2] for line in lines)
            if "worktree" not in fields:
                continue
            branch = fields.get("branch")
            linked.append(
                Linked(
                    path=fields["worktree"],
                    head=fields.get("HEAD", ""),
                    branch=branch.removeprefix("refs/heads/") if branch else None,
                    # The reason text is git's business; the fact is ours.
                    prunable=fields.get("prunable"),
                    locked="locked" in fields,
                )
            )
        return tuple(linked)

    def worktrees(self, store: Path) -> tuple[str, ...]:
        """The worktrees registered under this store.

        This is the guard `remove_object_store` reads, and a missing
        registered path cannot tell deleted from moved: a moved checkout's
        newest commits exist only in this store, its `.git` file still points
        here, and dropping the store destroys them without a word. So the
        guard counts registrations - the very thing a prune would act
        on - rather than guessing which ones stopped mattering.
        """
        return tuple(linked.path for linked in self.linked_worktrees(store))

    def is_dirty(self, worktree: Path) -> bool:
        """Tracked changes only.

        Untracked files are excluded because this is the flag a rebase refuses
        to run on, and an untracked scratch file blocks nothing. Build output
        cannot reach it either way: it is kept out of the source tree.
        """
        status = self._run(
            ("status", "--porcelain", "--untracked-files=no"),
            cwd=worktree,
            mutates=False,
            what="checking for local changes",
        )
        return bool(status.strip())

    def ahead_behind(self, worktree: Path, branch: str, remote: str) -> Tracking | None:
        """Drift against one remote's copy of this branch, or None if it has
        none - a branch that was never pushed, which is not an error."""
        counts = self._try(
            (
                "rev-list",
                "--left-right",
                "--count",
                f"refs/heads/{branch}...refs/remotes/{remote}/{branch}",
            ),
            cwd=worktree,
            what=f"comparing with {remote}",
        )
        parts = counts.split() if counts is not None else []
        if len(parts) != 2:
            return None
        return Tracking(remote=remote, ahead=int(parts[0]), behind=int(parts[1]))

    def fetch(self, store: Path, remote: str) -> None:
        # --prune so a branch deleted upstream does not linger as a stale
        # remote-tracking ref and quietly serve as somebody's base.
        self._run(
            ("fetch", "--quiet", "--prune", "--tags", remote),
            cwd=store,
            what=f"fetching from {remote}",
        )

    def detect_default_branch(self, store: Path, remote: str) -> None:
        """Record `refs/remotes/<remote>/HEAD`, which the sync commands read.

        Asking the remote rather than assuming `main`: every project happens
        to agree today, and that stays an observation rather than a constant.
        """
        self._run(
            ("remote", "set-head", remote, "--auto"),
            cwd=store,
            what="detecting the default branch",
        )

    def has_branch(self, store: Path, branch: str) -> bool:
        return (
            self._try(
                ("show-ref", "--verify", "--quiet", f"refs/heads/{branch}"),
                cwd=store,
                what=f"looking for {branch}",
            )
            is not None
        )

    def default_branch_ref(self, store: Path, remote: str) -> str | None:
        """The ref `init` recorded with `remote set-head`, or None. A ref
        rather than a name, because `worktree add` starts from it."""
        recorded = self._try(
            ("symbolic-ref", f"refs/remotes/{remote}/HEAD"),
            cwd=store,
            what="reading the default branch",
        )
        return recorded.strip() if recorded else None

    def add_worktree(
        self, store: Path, worktree: Path, branch: str, base: str | None
    ) -> None:
        """One checkout, on a new branch or on one that already exists.

        `--no-track`: the base is a remote-tracking ref of `upstream`, and
        tracking it would aim every later push at a read-only remote.
        """
        args = (
            ("worktree", "add", "--no-track", "-b", branch, str(worktree), base)
            if base is not None
            else ("worktree", "add", str(worktree), branch)
        )
        self._run(args, cwd=store, what=f"checking out {branch}")

    def remove_worktree(self, store: Path, worktree: Path) -> None:
        # Unchecked: after a failure there is often nothing to remove.
        # `--force` because git refuses a half-written checkout, which is
        # exactly the one this run has to take back.
        self._run(
            ("worktree", "remove", "--force", str(worktree)),
            cwd=store,
            check=False,
            what="removing the worktree",
        )

    def delete_branch(self, store: Path, branch: str) -> None:
        # Unchecked for the same reason: `worktree add -b` may have failed
        # before the branch existed, or after.
        self._run(
            ("branch", "-D", branch),
            cwd=store,
            check=False,
            what=f"deleting {branch}",
        )

    def _run(
        self,
        args: tuple[str, ...],
        *,
        cwd: Path,
        mutates: bool = True,
        what: str = "",
        check: bool = True,
    ) -> str:
        return self._executor.run(
            Command(argv=("git", *args), cwd=cwd, mutates=mutates, what=what),
            check=check,
        ).stdout

    def _try(self, args: tuple[str, ...], *, cwd: Path, what: str = "") -> str | None:
        """For a read-only query whose failure is itself an answer.

        Asking about a ref that does not exist is the normal case, not a
        broken workspace, so it must not surface as a `CommandError` the way a
        checked call would.
        """
        result = self._executor.run(
            Command(argv=("git", *args), cwd=cwd, mutates=False, what=what),
            check=False,
        )
        return result.stdout if result.ok else None


def provision_object_store(executor: Executor, store: Path, project: Project) -> None:
    """Create the bare store for one project and fill it from `upstream`.

    `git init` plus `remote add` plus `fetch` rather than `git clone --bare`:
    a bare clone writes the remote's branches straight into `refs/heads/*` and
    creates no `refs/remotes/*` at all, which would leave nothing to read the
    default branch back from, and nothing to fast-forward the local default
    branch *from*.

    `origin` is not wired here: creating or discovering a user's fork is a
    later milestone, and guessing its URL from a username would be wrong for
    anyone whose fork is named differently.
    """
    git = Git(executor)
    fresh = not (store / "HEAD").is_file()
    if fresh:
        git.init_bare(store)
    # A store that did not exist a moment ago has no remotes to list, and
    # under --dry-run it does not exist even now: `git init` was printed
    # rather than run, so probing inside it would fail on a missing directory.
    if fresh or UPSTREAM not in git.remotes(store):
        git.add_remote(store, UPSTREAM, project.upstream_url)
    git.fetch(store, UPSTREAM)
    git.detect_default_branch(store, UPSTREAM)


def remove_object_store(
    executor: Executor, fs: FileSystem, store: Path, project: Project
) -> None:
    """Drop a project from the workspace, fetched objects and all.

    Refuses while worktrees are still registered under the store, stale
    registrations included - why, see `worktrees`. The refusal names the way
    out: reconnect a moved checkout first, then `worktree prune` for the
    registrations whose directory is gone, run by the reader once satisfied
    they are really abandoned - nothing is pruned behind their back.
    """
    linked = Git(executor).worktrees(store)
    if linked:
        # The moved hint travels with the prune: the registered path cannot
        # tell deleted from moved (why, see `worktrees`), and this refusal is
        # where the reader decides - a bare prune here is the two-step path
        # to destroying a moved checkout's only copy of its newest commits.
        raise PreconditionError(
            f"{project.name} still has {len(linked)} worktree(s) registered: "
            f"{', '.join(linked)}. If one of them was moved rather than "
            f"deleted, `git -C {store} worktree repair <its new path>` "
            f"reconnects it first - prune would sever the moved checkout "
            f"from this store, where its newest commits exist. Then prune "
            f"the registrations whose directory is gone with "
            f"`git -C {store} worktree prune` (a locked one needs "
            f"`git -C {store} worktree unlock <path>` first) and remove one "
            f"still on disk with `git -C {store} worktree remove <path>`."
        )
    fs.remove(store)


def inspect_checkout(executor: Executor, probe: Probe) -> Held:
    """Everything the decision needs from one project's object store.

    Both sides of the comparison are resolved: git reports a worktree
    physically, so one reached through a symlink would look like a stranger's.
    """
    git = Git(executor)
    store = Path(probe.store)
    worktree = Path(probe.worktree).resolve()
    linked = {
        Path(entry.path).resolve(): entry
        # A dead registration must not read as a checkout here either: this
        # is the reader `branch new` decides from, and deciding from a ghost
        # would either report the branch set as present over a directory
        # that is not there or refuse `already checked out` naming a path
        # that does not exist. The same test `read_store` applies, so every
        # reader agrees on what is live.
        for entry in git.linked_worktrees(store)
        if not _dead(entry)
    }
    here = linked.get(worktree)
    return Held(
        project=probe.project,
        base=git.default_branch_ref(store, UPSTREAM),
        branch_exists=git.has_branch(store, probe.branch),
        checked_out=here.branch if here is not None else None,
        elsewhere=next(
            (
                path
                for path, entry in linked.items()
                if entry.branch == probe.branch and path != worktree
            ),
            None,
        ),
        occupied=here is None and _holds_something(worktree),
    )


def add_checkout(executor: Executor, enrolment: Enrolment) -> None:
    Git(executor).add_worktree(
        Path(enrolment.store),
        Path(enrolment.worktree),
        enrolment.branch,
        enrolment.base,
    )


def drop_checkout(executor: Executor, enrolment: Enrolment) -> None:
    """Take back one checkout this run created. The branch goes only if this
    run created it too: an adopted one outlives the branch set."""
    git = Git(executor)
    store = Path(enrolment.store)
    git.remove_worktree(store, Path(enrolment.worktree))
    if enrolment.action is Action.CREATE:
        git.delete_branch(store, enrolment.branch)


def _holds_something(path: Path) -> bool:
    """git creates the parent directories itself and accepts an existing empty
    one, so only a path with something in it is in the way."""
    if not path.exists():
        return False
    return not path.is_dir() or any(path.iterdir())


def read_store(executor: Executor, store: Path, project: str) -> StoreReading:
    """Everything `status` reads from one project's object store.

    One store's worth of queries, so that the caller's fan-out unit is the
    project and no two of these ever run against the same store at once. The
    queries are serial *within* it: git is being asked about one repository,
    and the win is across the six.

    Entries git can no longer enter come back beside the checkouts rather
    than inside them: git refuses every query that would have to enter such
    a worktree, so reading it as a checkout would fail the whole project for
    want of one stale registration - while dropping it silently would leave
    the report agreeing with a worktree it cannot see.
    """
    git = Git(executor)
    linked = git.linked_worktrees(store)
    return StoreReading(
        checkouts=tuple(
            Checkout(
                project=project,
                path=PurePath(entry.path),
                branch=entry.branch,
                head=entry.head,
                dirty=git.is_dirty(Path(entry.path)),
                # A detached worktree has no branch to compare, and asking
                # about `refs/heads/None` would be a query with no meaning.
                tracking=(
                    _drift(git, Path(entry.path), entry.branch)
                    if entry.branch is not None
                    else ()
                ),
            )
            for entry in linked
            if not _dead(entry)
        ),
        stale=tuple(
            _stale_registration(store, entry) for entry in linked if _dead(entry)
        ),
    )


def _dead(entry: Linked) -> bool:
    """Whether git will refuse to enter this worktree.

    Three facts, any of which is enough. `prunable`: the registration is
    broken - the directory may be gone, or may still hold the checkout with
    the work in it. Not a directory: a locked worktree is never marked
    `prunable` (a lock means "never prunable"), so a locked registration
    whose directory was removed arrives here only through this test. No
    `.git` file: the same lock also hides a checkout whose link file was
    clobbered while the directory still stands - git calls that one live,
    and entering it fails every query with `not a git repository`. Any one
    test alone misses an entry the others catch.
    """
    path = Path(entry.path)
    return (
        entry.prunable is not None or not path.is_dir() or not (path / ".git").is_file()
    )


def _stale_registration(store: Path, entry: Linked) -> StaleRegistration:
    """The stale registration as the report will name it: what is wrong, and
    the command that fixes it - the full `git -C <store>` form, because
    `git worktree` operates on the repository it runs in and the reader is
    not standing in the store."""

    def command(*args: str) -> str:
        return " ".join(("git", "-C", str(store), "worktree", *args))

    def moved_hint() -> str:
        # The one case the full-form rule does not settle: a bare `git
        # worktree repair` does not find a moved worktree even inside the
        # store (verified against git 2.55 - the entry stays prunable), so
        # the new location must be passed explicitly. Only the reader knows
        # that path; `<its new path>` stays theirs to fill in.
        return f"`{command('repair', '<its new path>')}` reconnects it first"

    moved = f"if the worktree was moved rather than deleted, {moved_hint()}"

    if Path(entry.path).is_dir():
        # The work in the directory is alive; only the registration broke -
        # the `.git` link file clobbered, say. `prunable` marks that unless
        # a lock suppresses it, so this branch takes the locked flavor too.
        # Calling it gone would send the reader to prune a live checkout;
        # git's remedy is repair, which reconnects just as well under a
        # lock - the lock survives the repair.
        fact = (
            "the checkout is still in the directory, but the registration "
            "does not point at it"
        )
        if entry.locked:
            fact += ", and the registration is locked"
        return StaleRegistration(
            path=PurePath(entry.path),
            fact=fact,
            remedy=command("repair", entry.path),
        )
    if entry.locked:
        return StaleRegistration(
            path=PurePath(entry.path),
            # A lock plus a missing directory is still ambiguous - deleted
            # or moved - and `unlock && prune` would sever a moved checkout
            # before it could be repaired, so the fact says what to
            # reconnect first.
            fact=(
                "the directory is gone from it, and the registration is "
                f"locked ({moved})"
            ),
            # `unlock` accepts a missing directory, so the pair runs as is.
            remedy=f"{command('unlock', entry.path)} && {command('prune')}",
        )
    return StaleRegistration(
        path=PurePath(entry.path),
        # The registered path is gone. If the worktree was moved rather than
        # deleted, plain prune would sever it: repair at the new location
        # reconnects the checkout first, and prune then finds nothing broken.
        fact=f"the directory is gone from it ({moved})",
        remedy=command("prune"),
    )


def _drift(git: Git, worktree: Path, branch: str) -> tuple[Tracking, ...]:
    found = (git.ahead_behind(worktree, branch, remote) for remote in REMOTES)
    return tuple(tracking for tracking in found if tracking is not None)
