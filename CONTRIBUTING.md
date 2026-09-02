# Contributing

## Prerequisites

[uv](https://docs.astral.sh/uv/) ≥ 0.8.22 is the only prerequisite. It manages Python
itself, the virtualenv, dependencies and builds — no `pip`, `pyenv` or `virtualenv`
needed.

## Setup

```bash
uv sync                                # creates .venv, installs the project and dev tools
git config core.hooksPath .githooks    # activates the git hooks
```

The second command is per-clone and cannot be versioned. Skip it and the hooks silently
never fire.

## Everyday commands

| Command | What it does |
| --- | --- |
| `uv run cjdev` | run the CLI from the working tree |
| `uv run pytest` | run the tests |
| `uv run pytest --cov` | ...with a coverage report |
| `uv run ruff check` | lint |
| `uv run ruff check --fix` | lint and autofix what can be autofixed |
| `uv run ruff format` | format |
| `uv run ty check` | type check |
| `uv run ty check -W` | type check in watch mode |
| `uv run cz commit` | write a commit message interactively |

Every tool is configured in [`pyproject.toml`](pyproject.toml); there are no separate
config files.

## Dependencies

Always go through `uv`. It edits `pyproject.toml`, re-resolves `uv.lock` and syncs
`.venv` in one step.

**Runtime dependency** — something the published package needs:

```bash
uv add typer
```

**Development dependency** — something only contributors need. It lands in the `dev`
group and is never shipped to users:

```bash
uv add --dev pytest-mock
```

**Removing:**

```bash
uv remove typer
```

**Upgrading:**

```bash
uv lock --upgrade-package typer && uv sync   # one package
uv lock --upgrade && uv sync                 # everything
```

**Inspecting:**

```bash
uv tree
```

Notes:

- Never `pip install` into `.venv`. Nothing would be recorded in `pyproject.toml` or
  `uv.lock`, and the next `uv sync` would wipe it out.
- Commit `pyproject.toml` and `uv.lock` together, in the same commit.
- `uv sync --locked` fails instead of updating the lock file — use it in CI to catch a
  stale `uv.lock`.
- `ty` is pinned with `==` on purpose. It is still `0.0.x`, so any release may break
  things; upgrade deliberately, not by accident.

### Adding a CLI dependency such as Typer

`uv add typer` only installs the package. The console script comes from
`[project.scripts]` in `pyproject.toml`:

```toml
[project.scripts]
cjdev = "cjdev:main"
```

That entry points at the `main` callable in `src/cjdev/__init__.py`, so keep a `main`
there and let it hand control to the Typer app:

```python
import typer

app = typer.Typer()


def main() -> None:
    app()
```

Adding new subcommands then needs no change to `pyproject.toml`.

## Git hooks

Plain git hooks in [`.githooks/`](.githooks), wired up through `core.hooksPath`. No hook
framework is involved.

`pre-commit` — fast, file-level checks, ~0.2 s:

```
ruff check · ruff format --check · ty check
```

`pre-push` — the same set plus the tests, i.e. the full CI gate:

```
ruff check · ruff format --check · ty check · pytest
```

`commit-msg` — validates the commit message with `cz check`.

The tests deliberately do not run on commit: `git rebase -i` replays `pre-commit` on
every rewritten commit, and a growing test suite would make rebasing painful. Broken
intermediate commits inside a branch are fine — nothing red reaches the remote.

When `pre-commit` fails on formatting or a lint rule:

```bash
uv run ruff check --fix && uv run ruff format
```

`git push --no-verify` bypasses the hook. Use it only when the failure is unrelated to
what you are pushing.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/), enforced by
[commitizen](https://commitizen-tools.github.io/commitizen/) on the `commit-msg` hook:

```
feat(cli): add build command
fix(git): handle detached HEAD
chore: bump ruff to 0.16.5
```

`uv run cz commit` walks you through the format interactively.

The message is not cosmetic — releases are derived from it, so pick the type honestly.

## Releases

`commitizen` reads the commit history, works out the next semantic version and updates
`version` in `pyproject.toml` along with the changelog:

```bash
uv run cz bump --dry-run    # preview the new version and changelog entry
uv run cz bump              # apply it, write CHANGELOG.md and create the git tag
```

`feat:` bumps the minor version, `fix:` the patch, and `!` or a `BREAKING CHANGE:`
footer the major. The project is on `major_version_zero`, so breaking changes bump the
minor while the version stays below 1.0.

## License

By contributing you agree that your contributions are dual-licensed under
[MIT](LICENSE-MIT) and [Apache-2.0](LICENSE-APACHE), matching the project.
