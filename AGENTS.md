# AGENTS.md

This file carries the repo's process to coding agents. What holds for the code is in
the docs, linked below — this file is how to work here, not what the code does.

## What this is

`cjdev` — Cangjie SDK developer utilities. A Python CLI (Typer, rich, tomlkit) that
manages multi-repository workspaces of the Cangjie SDK: branch sets across projects,
out-of-tree builds keyed by profile and environment, containerised builds, config
layering. Layered DDD: `domain/` (pure) ← `application/` ← `infra/` ← `cli/`.

## Setup

[uv](https://docs.astral.sh/uv/) is the only prerequisite.

```bash
uv sync                                # .venv + deps + dev tools
git config core.hooksPath .githooks    # per-clone, once
```

## Everyday commands

| Command | What it does |
| --- | --- |
| `uv run cjdev` | run the CLI from the working tree |
| `uv run pytest` | the tests |
| `uv run ruff check` / `ruff format --check` / `ty check` | lint, format, types |
| `uv run pytest tests/test_adr_index.py` | the ADR index freshness check |

Hooks: `pre-commit` (lint, ~0.2 s), `pre-push` (lint + tests), `commit-msg`
(conventional commits via `cz check`). Broken intermediate commits inside a branch
are fine — nothing red reaches the remote; CI enforces the same gates.

## The process

**Issue first, always** ([ADR-0009](docs/adr/0009-every-change-starts-with-an-issue.md)):
open the issue before the PR, link with a closing keyword (`Fixes #N`). The issue
keeps the why, the PR the how. Even a follow-up fix gets its issue.

**A real decision becomes an ADR** ([ADR-0024](docs/adr/0024-adrs-numbered-by-issue.md)):
one per file, ≤ 1 page, in `docs/adr/`, **numbered by the issue that decided it** —
never sequential. After adding one, regenerate the index and commit both:

```bash
python tools/adr_index.py
```

The index is generated, never hand-edited; a test fails CI when it is stale.

**The ADR number = the issue number is what keeps parallel PRs conflict-free**: the
number is allocated when the issue is created, before any PR exists.

## Before you change the code

- [docs/architecture.md](docs/architecture.md) — the layers, the ports, and the rules.
  An import from `domain` into `infra` is a bug, not a shortcut.
- [docs/conventions.md](docs/conventions.md) — the vocabulary. Mixing up *project* and
  *build unit* is the easiest way to write a wrong function.
- [docs/README.md](docs/README.md) — what the docs are, and when a change writes there.

Read what a change touches before changing it; the docs are short and load-bearing.
Never `pip install` into `.venv` — always `uv`. Commit `pyproject.toml` and `uv.lock`
together. Don't reformat or refactor outside the task's scope.

## Commits and PRs

Conventional Commits, enforced on `commit-msg`:

```
feat(cli): add build command
fix(git): handle detached HEAD
```

`uv run cz commit` writes one interactively. PRs are squash-merged; the PR **title**
becomes the commit on `master`, so it carries the type. The PR template's checklist is
what `pre-push` already runs.
