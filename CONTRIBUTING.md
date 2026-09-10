# Contributing

## Prerequisites

[uv](https://docs.astral.sh/uv/) ≥ 0.8.22 is the only prerequisite. It manages Python
itself, the virtualenv, dependencies and builds.

## Setup

```bash
uv sync                                # creates .venv, installs the project and dev tools
git config core.hooksPath .githooks    # activates the git hooks
```

The second command is per-clone and cannot be versioned.

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

Every tool is configured in [`pyproject.toml`](pyproject.toml).

## Before you change the code

- [`docs/architecture.md`](docs/architecture.md) - the layers, the ports, and the rules
  the code is holding to.
- [`docs/conventions.md`](docs/conventions.md) - the vocabulary, and what a comment is for.

## Dependencies

Always go through `uv`:

```bash
uv add typer                                 # runtime - shipped to users
uv add --dev pytest-mock                     # dev only - lands in the `dev` group
uv remove typer
uv lock --upgrade-package typer && uv sync   # upgrade one package
uv lock --upgrade && uv sync                 # upgrade everything
uv tree                                      # inspect
```

Notes:

- Never `pip install` into `.venv`. Nothing would be recorded in `pyproject.toml` or
  `uv.lock`, and the next `uv sync` would wipe it out.
- Commit `pyproject.toml` and `uv.lock` together, in the same commit.
- `uv sync --locked` fails instead of updating the lock file - use it in CI to catch a
  stale `uv.lock`.
- `ty` is pinned with `==` on purpose. It is still `0.0.x`, so any release may break
  things; upgrade deliberately, not by accident.
- `uv add` only installs a package. A new *console script* also needs an entry in
  `[project.scripts]`; a new subcommand of `cjdev` needs nothing there, see
  [the entry point](docs/architecture.md#the-entry-point).

## Git hooks

Plain git hooks in [`.githooks/`](.githooks), wired up through `core.hooksPath`. No hook
framework is involved.

- `pre-commit` - `ruff check · ruff format --check · ty check`, ~0.2 s.
- `pre-push` - the same plus `pytest`, i.e. the full CI gate.
- `commit-msg` - validates the message with `cz check`.

The tests deliberately do not run on commit: `git rebase -i` replays `pre-commit` on every
rewritten commit, and a growing test suite would make rebasing painful. Broken intermediate
commits inside a branch are fine - nothing red reaches the remote.

When `pre-commit` fails on formatting or a lint rule:

```bash
uv run ruff check --fix && uv run ruff format
```

`git push --no-verify` bypasses the hook. Use it only when the failure is unrelated to what
you are pushing.

## Issues and pull requests

Every change starts with an issue - even a follow-up fix to something that just merged. Open
the issue first, then the pull request, and link the pair with a closing keyword (`Fixes #N`
in the PR body): the merge closes the issue automatically, and the issue keeps the *why*
while the PR keeps the *how*. The issue and PR templates take care of the shape.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/), enforced by
[commitizen](https://commitizen-tools.github.io/commitizen/) on the `commit-msg` hook:

```
feat(cli): add build command
fix(git): handle detached HEAD
chore: bump ruff to 0.16.5
```

`uv run cz commit` walks you through the format interactively. The message is not
cosmetic - releases are derived from it, so pick the type honestly.

## Releases

`commitizen` reads the commit history, works out the next semantic version and updates
`version` in `pyproject.toml` along with the changelog:

```bash
uv run cz bump --dry-run    # preview the new version and changelog entry
uv run cz bump              # apply it, write CHANGELOG.md and create the git tag
```

`feat:` bumps the minor version, `fix:` the patch, and `!` or a `BREAKING CHANGE:` footer
the major. The project is on `major_version_zero`, so breaking changes bump the minor while
the version stays below 1.0.

## License

By contributing you agree that your contributions are dual-licensed under
[MIT](LICENSE-MIT) and [Apache-2.0](LICENSE-APACHE), matching the project.
