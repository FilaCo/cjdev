"""Third-party sources: fetched by cjdev before configure, linked by commit.

The decision is asserted on data. Fetching is asserted against a real tree with
a fake upstream, because a partial fetch and a rename are what it is about, and
the git half is asserted against a real repository served over `file://`.
"""

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePath, PurePosixPath

import pytest

from cjdev.application.third_party import (
    Found,
    Provision,
    Seen,
    decide,
    observe,
    provide,
)
from cjdev.domain.layout import WorkspaceLayout
from cjdev.domain.manifest import BuildUnit, ThirdParty
from cjdev.errors import CjdevError, CommandError, PreconditionError
from cjdev.infra.executor.host import HostExecutor
from cjdev.infra.filesystem import HostFileSystem
from cjdev.infra.git import fetch_commit, resolve_ref
from conftest import make_upstream

OLD = "1" * 40
NEW = "2" * 40
UPSTREAM = "https://example.invalid/boundscheck.git"
SOURCE = ThirdParty(
    path=PurePosixPath("third_party/boundscheck"), upstream=UPSTREAM, ref="main"
)


def compiler(*sources: ThirdParty) -> BuildUnit:
    return BuildUnit(
        name="compiler",
        project="cangjie_compiler",
        path=PurePosixPath("."),
        depends_on=(),
        third_party=sources,
    )


@contextmanager
def no_lock(path: PurePath) -> Iterator[None]:
    yield


class Upstream:
    """Resolves to `tip`, and fetches by writing a file - or by failing."""

    def __init__(self, tip: str | None = NEW, *, broken: bool = False) -> None:
        self.tip = tip
        self.broken = broken
        self.fetched: list[str] = []
        self.resolved = 0

    def resolve(self, cwd: PurePath, upstream: str, ref: str) -> str | None:
        self.resolved += 1
        if self.tip == "unreachable":
            raise CommandError(("git", "ls-remote"), str(cwd), 128, "no network")
        return self.tip

    def fetch(self, into: PurePath, upstream: str, commit: str) -> None:
        assert not Path(into).exists(), "fetched into a directory that was there"
        Path(into).mkdir()
        if self.broken:
            raise CommandError(("git", "fetch"), str(into), 128, "early EOF")
        (Path(into) / "src").write_text(commit)
        self.fetched.append(commit)


@pytest.fixture
def workspace(tmp_path: Path) -> WorkspaceLayout:
    layout = WorkspaceLayout(tmp_path)
    Path(layout.worktree("main", "cangjie_compiler") / "third_party").mkdir(
        parents=True
    )
    return layout


def planned(layout: WorkspaceLayout, unit: BuildUnit) -> tuple[Provision, ...]:
    return decide(layout, "main", unit, observe(layout, "main", unit))


def run(provision: Provision, upstream: Upstream) -> None:
    provide(
        provision,
        resolve=upstream.resolve,
        fetch=upstream.fetch,
        file_system=HostFileSystem(),
        lock=no_lock,
    )


def link_of(layout: WorkspaceLayout) -> Path:
    return Path(layout.worktree("main", "cangjie_compiler") / SOURCE.path)


class TestDecide:
    LAYOUT = WorkspaceLayout(PurePath("/ws"))

    def test_the_link_is_where_upstream_looks_and_the_store_is_shared(self):
        # Act
        (provision,) = decide(self.LAYOUT, "main", compiler(SOURCE), ())

        # Assert
        assert provision.link == PurePath(
            "/ws/main/cangjie_compiler/third_party/boundscheck"
        )
        assert provision.store == PurePath("/ws/.cjdev/cache/third_party/boundscheck")
        assert provision.linked is None

    def test_what_is_linked_now_is_carried_to_the_fetch(self):
        # Act
        (provision,) = decide(
            self.LAYOUT,
            "main",
            compiler(SOURCE),
            (Seen(SOURCE.path, Found.OURS, OLD),),
        )

        # Assert
        assert provision.linked == OLD

    def test_a_directory_cjdev_did_not_fetch_is_refused_with_the_way_out(self):
        # Upstream's own clone looks the same whether it finished or not, and
        # trusting a partial one is the "No SOURCES given" dead end.
        # Act
        with pytest.raises(PreconditionError) as refused:
            decide(
                self.LAYOUT,
                "main",
                compiler(SOURCE),
                (Seen(SOURCE.path, Found.FOREIGN),),
            )

        # Assert
        link = "/ws/main/cangjie_compiler/third_party/boundscheck"
        assert refused.value.remedy == f"rm -rf {link}"
        assert refused.value.subject == "compiler"


class TestObserve:
    def test_a_real_directory_is_foreign(self, workspace: WorkspaceLayout):
        # Arrange
        link_of(workspace).mkdir()

        # Act
        (seen,) = observe(workspace, "main", compiler(SOURCE))

        # Assert
        assert seen.found is Found.FOREIGN

    def test_a_link_somewhere_else_is_foreign(
        self, workspace: WorkspaceLayout, tmp_path: Path
    ):
        # Arrange
        (tmp_path / "mine").mkdir()
        link_of(workspace).symlink_to(tmp_path / "mine")

        # Act
        (seen,) = observe(workspace, "main", compiler(SOURCE))

        # Assert
        assert seen.found is Found.FOREIGN

    def test_a_dangling_link_of_ours_names_no_commit(self, workspace: WorkspaceLayout):
        # Arrange
        link_of(workspace).symlink_to(
            Path(workspace.third_party_dir("boundscheck") / OLD)
        )

        # Act
        (seen,) = observe(workspace, "main", compiler(SOURCE))

        # Assert
        assert seen == Seen(SOURCE.path, Found.OURS, None)


class TestProvide:
    def test_a_fetch_is_linked_relatively_once_it_is_complete(
        self, workspace: WorkspaceLayout
    ):
        # Arrange
        upstream = Upstream()
        (provision,) = planned(workspace, compiler(SOURCE))

        # Act
        run(provision, upstream)

        # Assert
        link = link_of(workspace)
        assert not link.readlink().is_absolute()
        assert (link / "src").read_text() == NEW
        assert not Path(provision.store / f"{NEW}.partial").exists()

    def test_a_partial_fetch_is_started_over_rather_than_trusted(
        self, workspace: WorkspaceLayout
    ):
        # Arrange: what a Ctrl-C mid-fetch leaves.
        upstream = Upstream()
        (provision,) = planned(workspace, compiler(SOURCE))
        partial = Path(provision.store / f"{NEW}.partial")
        partial.mkdir(parents=True)
        (partial / ".git").mkdir()

        # Act
        run(provision, upstream)

        # Assert
        assert upstream.fetched == [NEW]
        assert (link_of(workspace) / "src").read_text() == NEW

    def test_a_fetched_commit_is_not_fetched_again(self, workspace: WorkspaceLayout):
        # Arrange
        run(planned(workspace, compiler(SOURCE))[0], Upstream())
        upstream = Upstream()

        # Act
        run(planned(workspace, compiler(SOURCE))[0], upstream)

        # Assert
        assert upstream.fetched == []

    def test_a_moved_tip_is_fetched_beside_the_old_one(
        self, workspace: WorkspaceLayout
    ):
        # Arrange
        run(planned(workspace, compiler(SOURCE))[0], Upstream(OLD))

        # Act
        run(planned(workspace, compiler(SOURCE))[0], Upstream(NEW))

        # Assert
        store = Path(workspace.third_party_dir("boundscheck"))
        assert {OLD, NEW} <= {entry.name for entry in store.iterdir()}
        assert (link_of(workspace) / "src").read_text() == NEW

    def test_a_failed_fetch_is_an_error_with_a_remedy_and_links_nothing(
        self, workspace: WorkspaceLayout
    ):
        # Arrange
        (provision,) = planned(workspace, compiler(SOURCE))

        # Act
        with pytest.raises(CjdevError) as failed:
            run(provision, Upstream(broken=True))

        # Assert
        assert failed.value.remedy == "cjdev build compiler"
        assert "early EOF" in str(failed.value)
        assert not link_of(workspace).is_symlink()
        assert not Path(provision.store / NEW).exists()

    def test_offline_keeps_what_is_linked(self, workspace: WorkspaceLayout):
        # Arrange
        run(planned(workspace, compiler(SOURCE))[0], Upstream(OLD))
        upstream = Upstream("unreachable")

        # Act
        run(planned(workspace, compiler(SOURCE))[0], upstream)

        # Assert
        assert upstream.fetched == []
        assert (link_of(workspace) / "src").read_text() == OLD

    def test_offline_with_nothing_fetched_says_so(self, workspace: WorkspaceLayout):
        # Arrange
        (provision,) = planned(workspace, compiler(SOURCE))

        # Act
        with pytest.raises(CjdevError) as failed:
            run(provision, Upstream("unreachable"))

        # Assert
        assert failed.value.remedy == "cjdev build compiler"

    def test_a_ref_upstream_does_not_have_is_refused(self, workspace: WorkspaceLayout):
        # Arrange
        (provision,) = planned(workspace, compiler(SOURCE))

        # Act
        with pytest.raises(PreconditionError):
            run(provision, Upstream(None))

    def test_a_pinned_commit_is_not_resolved(self, workspace: WorkspaceLayout):
        # Arrange
        upstream = Upstream()
        pinned = ThirdParty(SOURCE.path, UPSTREAM, OLD)

        # Act
        run(planned(workspace, compiler(pinned))[0], upstream)

        # Assert
        assert upstream.resolved == 0
        assert upstream.fetched == [OLD]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.mark.usefixtures("git_available")
class TestGit:
    def test_a_branch_resolves_to_its_tip(self, tmp_path: Path):
        # Arrange
        url = make_upstream(tmp_path / "up")

        # Act
        commit = resolve_ref(HostExecutor(), tmp_path, url, "main")

        # Assert
        assert commit == git(tmp_path / "up", "rev-parse", "HEAD")

    def test_an_annotated_tag_resolves_to_its_commit(self, tmp_path: Path):
        # Arrange
        url = make_upstream(tmp_path / "up")
        git(tmp_path / "up", "tag", "-a", "-m", "release", "v1")

        # Act
        commit = resolve_ref(HostExecutor(), tmp_path, url, "v1")

        # Assert
        assert commit == git(tmp_path / "up", "rev-parse", "HEAD")

    def test_a_missing_ref_is_none_rather_than_an_error(self, tmp_path: Path):
        # Arrange
        url = make_upstream(tmp_path / "up")

        # Act
        commit = resolve_ref(HostExecutor(), tmp_path, url, "nope")

        # Assert
        assert commit is None

    def test_a_commit_behind_the_tip_is_fetched_and_checked_out(self, tmp_path: Path):
        # Arrange
        upstream = tmp_path / "up"
        url = make_upstream(upstream)
        first = git(upstream, "rev-parse", "HEAD")
        (upstream / "later").write_text("later")
        git(upstream, "add", "later")
        git(upstream, "commit", "--quiet", "-m", "later")
        (tmp_path / "store").mkdir()

        # Act
        fetch_commit(HostExecutor(), tmp_path / "store" / first, url, first)

        # Assert
        tree = tmp_path / "store" / first
        assert git(tree, "rev-parse", "HEAD") == first
        assert not (tree / "later").exists()
