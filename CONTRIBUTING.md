# Contributing

## Prerequisites

[uv](https://docs.astral.sh/uv/) ≥ 0.8.22 is the only prerequisite. It manages Python
itself, the virtualenv, dependencies and builds - no `pip`, `pyenv` or `virtualenv`
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

**Runtime dependency** - something the published package needs:

```bash
uv add typer
```

**Development dependency** - something only contributors need. It lands in the `dev`
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
- `uv sync --locked` fails instead of updating the lock file - use it in CI to catch a
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

## Code layout

The layers come from [`docs/requirements.md`](docs/requirements.md) §7.6, and the import
direction is the point of them: `domain` depends on nothing of ours except `errors`,
`application` depends on `domain` and on its own ports, `infra` and `cli` depend inwards.
An `import` from `domain` into `infra` is a bug, not a shortcut.

`errors.py` sits *below* `domain` - it imports nothing at all, so every layer may raise
from it. It is the only module with that position, and adding a second one is how the
layering quietly stops meaning anything.

`cjdev` orchestrates external processes and owns no business rules, so the core is
deliberately thin: data and pure functions, not aggregates with lifecycles. No entities
with private state, no repositories, no CQRS split - those cost structure and buy nothing
when the entire persistent state is a handful of files this tool wrote itself.

```
src/cjdev/
  __init__.py              # main(); the console script entry point
  bootstrap.py             # composition root - assembles executor, forge, use cases
  errors.py                # error hierarchy → exit codes (UX-5)

  domain/                  # pure: no subprocess, no filesystem, no network (NFR-2)
    manifest.py            # Project, BuildUnit and the build graph (§4.3)
    layout.py              # workspace path algebra, parameterised by root (§4.1)
    state.py               # branch / SHA / dirty / ahead-behind

  application/             # orchestration and policy; one module per command
    ports.py               # Executor, FileSystem, Prompt, Forge - nothing else
    runner.py              # fan-out, -j, output ordering, cancellation (§5.10)
    init_workspace.py
    report_status.py

  infra/                   # the only layer that touches the outside world
    executor/              # build_executor(); hides the decorator order
      host.py  log.py  dry_run.py
    git.py                 # argv for git, and parsing its output (NFR-3)
    config.py              # layered config + manifest loading (CFG-1/2/3)
    data/default_manifest.toml      # the shipped manifest; travels in the wheel

  cli/                     # Typer wiring, thin by construction
    _context.py            # the typed Context
    _console.py            # one Console, and the marks for ok/failed/cancelled
    _progress.py           # the live display, and per-unit output capture
    _render.py             # summaries and --json (UX-6, UX-8)
    init.py  clean.py  status.py  build.py

### Terminal output

`rich` renders it. It is a real dependency rather than hand-rolled ANSI because UX-8 asks
for a stable live display while six things run at once, and because the fallbacks - width
detection, colour support, a pipe or a CI log getting plain text - are exactly the part
that is tedious to get right and invisible when wrong.

Two rules for it. **Marks, not emoji**: `✓`, `✗` and `-` say how something ended, line up
in a column and mean the same thing to everyone; a picture of a rocket does neither. And
**a worker never prints**. Under `-j` the order things happen in belongs to the scheduler,
and the transcript is not allowed to (PAR-4), so command output is captured per unit and
rendered afterwards in manifest order. The live display is the one thing allowed to be
concurrent, and it draws only status.
```

### Four ports, and only four

A port is earned by a second implementation that will actually exist: `Executor` (host,
then container), `FileSystem` (real, or dry-run), `Prompt` (a terminal, or
`--defaults`/`--yes`/a pipe) and `Forge` (gitcode, then one more to prove it). Nothing
else is one.

Note what three of those have in common: their second implementation is a flag the user
passes, not a seam invented for tests. **If a proposed port's second implementation only
ever appears in a test file, it is not a port.**

`FileSystem` earned its place the hard way. `init --dry-run` created the workspace it was
supposed to only describe, because the executor covers subprocesses and `Path.mkdir` is
not one. Anything that changes the tree goes through the port; anything that only reads it
does not, since a probe has to be real or the plan is built on guesses.

Git in particular is **not** a port. NFR-3 already commits to driving the `git` CLI, and
the CLI runs through `Executor`; a second abstraction over the same subprocess is a tax
with no payer. `infra/git.py` builds argv and parses output, and is tested against real
git in a `tmp_path`, which is fast enough not to need a fake.

### Use cases are gather → decide → apply

A use case reads the world, computes a decision purely, then applies it. Keeping the
middle phase pure is what makes preflight (BRANCH-8), `--dry-run` (UX-1) and the tests
possible at all: the decision can be asserted on without git, network or containers.
Complex flows are a sequence of such phases, not one big pure function - resist the urge
to make the whole command pure, and resist the urge to interleave the three.

### Concurrency lives in `application/runner.py`

Commands hand the runner a list of independent units of work; they never spawn threads
themselves (PAR-1). `-j`, output ordering, cancellation and the per-unit summary are
implemented once, there. Two units touching the same object store must not run
concurrently - the fan-out key is the project for git work and the build unit for builds
(PAR-2).

### File or folder?

**A folder is warranted when there is something to hide.** Its `__init__.py` is a
decision about what does *not* escape. If that file would just re-export everything
inside, the folder bought nothing and cost a segment on every import.

`infra/executor/` passes the test: the caller gets `build_executor()` and never learns
that the stack is dry-run over logging over host. `infra/git.py` is a single file for
the same reason - a folder holding one module is just a module with extra steps.

CLI modules are always files, never packages. A CLI module is Typer wiring; five
subcommands are ~120 lines of the same shape, which reads better in one file than in
five. The inverse is the useful rule: **if a CLI module grows enough to want a folder,
logic has leaked into it that belongs in `application/`** - the folder would hide a
layering violation rather than organise anything.

A related smell, and one this project actually grew: a command file with one subcommand
per manifest entry. `build.py` was thirteen near-identical stubs against a manifest of
four units, and the two had already drifted. One command that takes its names *from* the
manifest cannot drift, and gets completion for free (UX-7). If you are about to write the
same command shape N times, the N belongs in data.

`domain/` and `application/` are folders for a different reason. They are not grouping
related files; they are the layer boundaries that review and `ty` check against.

### Comments answer "why", never "what"

The code already says what it does; a comment repeating that is a second copy to keep in
sync, and it goes stale silently. So a comment earns its place only by carrying something
the code cannot: the reason a decision was made, the requirement it satisfies, the
alternative that was rejected and why, or the non-obvious behaviour of something else that
forced this shape.

```python
# No. Restates the line below.
# Flatten the branch set name and join it to the root.
return self.root / flatten_branch_set(branch_set)

# Yes. Explains a constraint that is invisible here.
# `Path` folds `.` away entirely, so a name of "." arrives with no parts at
# all and would otherwise resolve to the parent directory.
```

Section banners (`# --- validation ---`) are the same mistake in a costume: they label
what follows, which the reader can already see. If a file needs them to stay navigable, it
is telling you it wants to be two files.

The same rule governs docstrings. `"""The repository name, e.g. cangjie_compiler."""`
earns its place by giving a concrete example a bare `value: str` cannot; a docstring that
restates the function name does not. Typer command docstrings are the exception - they are
user-facing help text, not commentary.

In tests, "why" is usually the requirement under test. Naming it (`CACHE-1`, `PAR-4`,
`R11`) turns an assertion that looks arbitrary into one a reader can check against the
spec, and makes it obvious what breaks if the requirement changes.

### Names

The vocabulary is [`docs/requirements.md`](docs/requirements.md) §2, and the code uses it
verbatim. **Project** is one git repository - the unit of cloning, branching and PR
creation. **Build unit** is one buildable subproject inside a project; a project may hold
several, and the dependency graph is over units, never over projects. Getting these two
mixed up is the single easiest way to write a wrong requirement or a wrong function.

### TOML

`tomlkit` is the only TOML library used, for reading and writing alike.

`tomllib` would cost nothing, but it is read-only and 3.11+, and `cjdev` writes TOML:
`.cjdev/config.toml` at `init` and again on every `cjdev config set`. A reader plus a
writer plus a `python_version` marker costs more than the single dependency saves - and
comment and key-order preservation is not a nicety here: `config.toml` is a file the user
edits by hand *and* `cjdev` writes into, so regenerating it would throw away their
comments and their ordering every time.

The price is that `tomlkit` returns `TOMLDocument`, not `dict`. Keep it inside `infra/`:
`config.py` converts to the `domain/` dataclasses at the boundary, and
no `TOMLDocument` reaches `application/` or `domain/`.

### Bundled data

`infra/data/` is a plain directory, not a package. Reach it through the anchor package:

```python
from importlib.resources import files

files("cjdev.infra") / "data" / "default_manifest.toml"
```

`uv_build` ships non-Python files under the module root, so the TOML lands in the wheel.
It is still worth a test that loads it through `importlib.resources` rather than from
the working tree - otherwise a packaging regression shows up only for users.

## Git hooks

Plain git hooks in [`.githooks/`](.githooks), wired up through `core.hooksPath`. No hook
framework is involved.

`pre-commit` - fast, file-level checks, ~0.2 s:

```
ruff check · ruff format --check · ty check
```

`pre-push` - the same set plus the tests, i.e. the full CI gate:

```
ruff check · ruff format --check · ty check · pytest
```

`commit-msg` - validates the commit message with `cz check`.

The tests deliberately do not run on commit: `git rebase -i` replays `pre-commit` on
every rewritten commit, and a growing test suite would make rebasing painful. Broken
intermediate commits inside a branch are fine - nothing red reaches the remote.

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

The message is not cosmetic - releases are derived from it, so pick the type honestly.

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
