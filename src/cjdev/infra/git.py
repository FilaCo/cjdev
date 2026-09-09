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
from cjdev.domain.state import Checkout, Tracking
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
                )
            )
        return tuple(linked)

    def worktrees(self, store: Path) -> tuple[str, ...]:
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
        """The ref `init` recorded with `remote set-head`, or None.

        A ref rather than a branch name, because it is handed straight to
        `worktree add` as the point to start from.
        """
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

        `--no-track` is not tidiness: the base is a remote-tracking ref of
        `upstream`, and letting git wire the branch up to it would aim every
        later push at the repository cjdev only ever reads.
        """
        args = (
            ("worktree", "add", "--no-track", "-b", branch, str(worktree), base)
            if base is not None
            else ("worktree", "add", str(worktree), branch)
        )
        self._run(args, cwd=store, what=f"checking out {branch}")

    def remove_worktree(self, store: Path, worktree: Path) -> None:
        # Unchecked, because after a failure there may be no worktree to
        # remove and that is the normal case rather than an error. `--force`
        # because a checkout that failed halfway is exactly the one git would
        # otherwise refuse to remove - and it is one this run created.
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

    Refuses while worktrees are linked to the store: deleting it under them
    leaves checkouts whose git metadata points at nothing, which is worse than
    the state the user was trying to leave.
    """
    linked = Git(executor).worktrees(store)
    if linked:
        raise PreconditionError(
            f"{project.name} still has {len(linked)} worktree(s): "
            f"{', '.join(linked)}. Remove those first."
        )
    fs.remove(store)


def inspect_checkout(executor: Executor, probe: Probe) -> Held:
    """Everything the decision needs from one project's object store.

    Paths are resolved on both sides before they are compared: git reports a
    worktree physically, so one reached through a symlink would otherwise look
    like a stranger's directory sitting in the way.
    """
    git = Git(executor)
    store = Path(probe.store)
    worktree = Path(probe.worktree).resolve()
    linked = {
        Path(entry.path).resolve(): entry for entry in git.linked_worktrees(store)
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
    """Take back one checkout this run created.

    The branch goes only when this run is what created it: an adopted branch
    outlives the branch set, which is the whole reason adoption exists.
    """
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


def read_checkouts(
    executor: Executor, store: Path, project: str
) -> tuple[Checkout, ...]:
    """Every worktree of one project, with the state `status` reports.

    One store's worth of queries, so that the caller's fan-out unit is the
    project and no two of these ever run against the same store at once. The
    queries are serial *within* it: git is being asked about one repository,
    and the win is across the six.
    """
    git = Git(executor)
    return tuple(
        Checkout(
            project=project,
            path=PurePath(linked.path),
            branch=linked.branch,
            head=linked.head,
            dirty=git.is_dirty(Path(linked.path)),
            # A detached worktree has no branch to compare, and asking about
            # `refs/heads/None` would be a query with no meaning.
            tracking=(
                _drift(git, Path(linked.path), linked.branch)
                if linked.branch is not None
                else ()
            ),
        )
        for linked in git.linked_worktrees(store)
    )


def _drift(git: Git, worktree: Path, branch: str) -> tuple[Tracking, ...]:
    found = (git.ahead_behind(worktree, branch, remote) for remote in REMOTES)
    return tuple(tracking for tracking in found if tracking is not None)
