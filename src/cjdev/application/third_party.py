"""A unit's third-party sources, fetched before its build configures.

Upstream's configure clones them itself and checks nothing: an interrupted
clone leaves a directory that every later configure trusts. So cjdev fetches
them first, into `.cjdev/cache/third_party/<name>/<commit>/`, and the path
upstream's configure looks for is a link to that commit. A commit's directory
exists only once its fetch completed - it is fetched beside it and renamed into
place last - so a partial fetch is never linked, and the next run starts over.

Keyed by commit rather than by ref, because a branch moves: a moved tip is
fetched beside the old one, and only the link changes.
"""

import os
import re
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import Enum, auto, unique
from pathlib import Path, PurePath, PurePosixPath
from typing import final

from cjdev.application.ports import FileSystem
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import BuildUnit
from cjdev.errors import CjdevError, CommandError, PreconditionError

Resolve = Callable[[PurePath, str, str], str | None]
"""The commit `ref` names at `upstream` now, asked from a working directory;
`None` when the upstream has no such ref."""

Fetch = Callable[[PurePath, str, str], None]
"""One commit of `upstream`, checked out into a directory that does not exist
yet."""

Lock = Callable[[PurePath], AbstractContextManager[None]]

COMMIT = re.compile(r"[0-9a-f]{40}")


@final
@unique
class Found(Enum):
    ABSENT = auto()
    OURS = auto()
    """A link into the source's own directory under the cache."""
    FOREIGN = auto()
    """A real directory, or a link cjdev did not write."""


@final
@dataclass(frozen=True)
class Seen:
    path: PurePosixPath
    found: Found
    commit: str | None = None
    """The fetched commit an OURS link names. None when it names one that is
    not there: a dangling link is as good as absent."""


@final
@dataclass(frozen=True)
class Provision:
    unit: str
    name: str
    upstream: str
    ref: str
    link: PurePath
    store: PurePath
    linked: str | None
    """The commit the link names now."""


def observe(
    layout: WorkspaceLayout, branch_set: str, unit: BuildUnit
) -> tuple[Seen, ...]:
    return tuple(
        _seen(layout, _link(layout, branch_set, unit, source.path), source.path)
        for source in unit.third_party
    )


def decide(
    layout: WorkspaceLayout,
    branch_set: str,
    unit: BuildUnit,
    seen: tuple[Seen, ...],
) -> tuple[Provision, ...]:
    found: Mapping[PurePosixPath, Seen] = {entry.path: entry for entry in seen}
    planned = []
    for source in unit.third_party:
        link = _link(layout, branch_set, unit, source.path)
        entry = found.get(source.path, Seen(source.path, Found.ABSENT))
        if entry.found is Found.FOREIGN:
            # Most likely upstream's own clone, and nothing tells a complete
            # one from the remains of an interrupted one.
            raise PreconditionError(
                f"{link} is not a fetch cjdev made, so nothing says it is "
                f"complete; cjdev fetches {source.name} itself now.",
                subject=unit.name,
                remedy=f"rm -rf {link}",
            )
        planned.append(
            Provision(
                unit=unit.name,
                name=source.name,
                upstream=source.upstream,
                ref=source.ref,
                link=link,
                store=layout.third_party_dir(source.name),
                linked=entry.commit,
            )
        )
    return tuple(planned)


def provide(
    provision: Provision,
    *,
    resolve: Resolve,
    fetch: Fetch,
    file_system: FileSystem,
    lock: Lock,
) -> None:
    """Resolve, fetch what is missing, link."""
    commit = _resolved(provision, resolve)
    tree = provision.store / commit
    if not Path(tree).is_dir():
        with lock(provision.store / f"{commit}.lock"):
            partial = provision.store / f"{commit}.partial"
            if Path(partial).exists():
                file_system.remove(partial)
            file_system.mkdir(provision.store)
            try:
                fetch(partial, provision.upstream, commit)
            except CommandError as failure:
                raise CjdevError(
                    f"fetching {provision.name} {commit} from "
                    f"{provision.upstream} failed, so nothing was linked.\n"
                    f"{failure.tail}",
                    subject=provision.unit,
                    remedy=f"cjdev build {provision.unit}",
                ) from failure
            file_system.move(partial, tree)
    if commit != provision.linked:
        # Relative, so it resolves at whatever path a container mounts the
        # workspace at.
        file_system.symlink(
            provision.link, PurePath(os.path.relpath(tree, provision.link.parent))
        )


def _resolved(provision: Provision, resolve: Resolve) -> str:
    if COMMIT.fullmatch(provision.ref):
        return provision.ref
    try:
        # From the worktree, the one directory here certain to exist already.
        commit = resolve(provision.link.parent, provision.upstream, provision.ref)
    except CommandError as failure:
        # Offline is not a failed fetch: what is linked is complete, and it
        # is what upstream's configure would have built with too.
        if provision.linked is not None:
            return provision.linked
        raise CjdevError(
            f"cannot reach {provision.upstream} to resolve {provision.ref}, "
            f"and no {provision.name} has been fetched yet.\n{failure.tail}",
            subject=provision.unit,
            remedy=f"cjdev build {provision.unit}",
        ) from failure
    if commit is None:
        raise PreconditionError(
            f"{provision.upstream} has no branch or tag {provision.ref}.",
            subject=provision.unit,
            remedy="set its third_party ref in .cjdev/config.toml",
        )
    return commit


def _link(
    layout: WorkspaceLayout, branch_set: str, unit: BuildUnit, path: PurePosixPath
) -> PurePath:
    return layout.worktree(branch_set, unit.project) / unit.path / path


def _seen(layout: WorkspaceLayout, link: PurePath, path: PurePosixPath) -> Seen:
    here = Path(link)
    if here.is_symlink():
        target = PurePath(os.path.normpath(link.parent / here.readlink()))
        store = layout.third_party_dir(path.name)
        if target.parent != store:
            return Seen(path, Found.FOREIGN)
        fetched = here.is_dir() and COMMIT.fullmatch(target.name)
        return Seen(path, Found.OURS, target.name if fetched else None)
    if here.exists():
        return Seen(path, Found.FOREIGN)
    return Seen(path, Found.ABSENT)
