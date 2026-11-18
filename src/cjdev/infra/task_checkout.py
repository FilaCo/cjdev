"""Git state needed to publish and retire a multi-project task."""

from dataclasses import dataclass
from pathlib import Path

from cjdev.application.ports import Command, Executor
from cjdev.application.workspace import enrolled_projects
from cjdev.domain.forge import Repository, parse_repository
from cjdev.domain.fork import web_page
from cjdev.domain.layout import WorkspaceLayout, flatten_branch_set
from cjdev.domain.manifest import Manifest
from cjdev.errors import PreconditionError
from cjdev.infra.git import Git
from cjdev.infra.gitcode import GitCodeForge


@dataclass(frozen=True)
class Checkout:
    path: Path
    store: Path
    branch: str
    sha: str
    base: str
    repo: Repository
    ahead: int


def inspect(
    executor: Executor, layout: WorkspaceLayout, name: str, manifest: Manifest
) -> list[Checkout]:
    git = Git(executor)
    result = []
    for project in enrolled_projects(layout, manifest, name):
        path = Path(layout.worktree(name, project))
        store = Path(layout.object_store(project))

        def read(*args: str, cwd: Path = path) -> str:
            return executor.run(
                Command(("git", *args), cwd, mutates=False)
            ).stdout.strip()

        base = git.default_branch_ref(store, "upstream")
        branch = git.current_branch(path)
        if (
            not base
            or not branch
            or flatten_branch_set(branch) != name
            or branch == base.removeprefix("refs/remotes/upstream/")
            or Path(
                read("rev-parse", "--path-format=absolute", "--git-common-dir")
            ).resolve()
            != store.resolve()
            or Path(read("rev-parse", "--show-toplevel")).resolve() != path
        ):
            raise PreconditionError(f"{path} is not the expected task checkout")
        if read("status", "--porcelain", "--untracked-files=all"):
            raise PreconditionError(f"{path} has uncommitted changes")
        repo = parse_repository(manifest.project(project).upstream_url)
        result.append(
            Checkout(
                path,
                store,
                branch,
                read("rev-parse", "HEAD"),
                base.removeprefix("refs/remotes/upstream/"),
                repo,
                git.count(path, "HEAD", base),
            )
        )
    return result


def fork_owner(executor: Executor, checkout: Checkout) -> str:
    origin = executor.run(
        Command(
            ("git", "remote", "get-url", "--push", "--all", "origin"),
            checkout.path,
            mutates=False,
        )
    ).stdout.strip()
    fork = parse_repository(web_page(origin) or "")
    if (
        len(origin.splitlines()) != 1
        or fork.host != "gitcode.com"
        or fork.host != checkout.repo.host
        or fork.owner.casefold() == checkout.repo.owner.casefold()
        or fork.name != checkout.repo.name
    ):
        raise PreconditionError(
            f"{checkout.path}: origin must point to a fork of {checkout.repo.url}"
        )
    return fork.owner


def publish(
    executor: Executor, forge: GitCodeForge, checkout: Checkout, issue: str
) -> str:
    owner = fork_owner(executor, checkout)
    title = executor.run(
        Command(
            ("git", "log", "-1", "--format=%s", checkout.sha),
            checkout.path,
            mutates=False,
        )
    ).stdout.strip()
    executor.run(
        Command(
            ("git", "push", "origin", f"{checkout.sha}:refs/heads/{checkout.branch}"),
            checkout.path,
        )
    )
    return forge.publish(
        checkout.repo, owner, checkout.branch, checkout.base, title, issue
    )


def retire(
    executor: Executor,
    forge: GitCodeForge,
    checkouts: list[Checkout],
    layout: WorkspaceLayout,
    name: str,
) -> None:
    directory = Path(layout.branch_set_dir(name))
    if set(directory.iterdir()) != {item.path for item in checkouts}:
        raise PreconditionError(
            f"{directory} contains files outside the project checkouts"
        )
    for item in checkouts:
        if item.ahead:
            pr = forge.pull(
                item.repo,
                fork_owner(executor, item),
                item.branch,
                item.base,
                merged=True,
            )
            if not pr or not pr.get("merged_at") or pr["head"]["sha"] != item.sha:
                raise PreconditionError(f"{item.path}: no merged PR for {item.sha}")
    for item in checkouts:
        executor.run(Command(("git", "worktree", "remove", str(item.path)), item.store))
        executor.run(
            Command(
                ("git", "update-ref", "-d", f"refs/heads/{item.branch}", item.sha),
                item.store,
            )
        )
    directory.rmdir()
