# ADR-0005: CI mirrors the local gates, and the wheel is proven installable

Status: accepted, 2026-09-10. Closes #5.

## Context

The repo had a full local quality gate — `.githooks` pre-commit (`ruff check`,
`ruff format --check`, `ty check`) and pre-push (the same plus `pytest`) — and nothing
enforced any of it on the remote: `git push --no-verify` or a careless direct push
landed green no matter what, and there was no way to grab a build of `master`.

## Decision

One workflow, `.github/workflows/ci.yml`, on `push` to `master` and on all pull
requests: three jobs that mirror the hooks rather than invent a second standard —
lint (ruff check, ruff format --check, ty check), test (pytest on a 3.10/3.13 matrix),
and build (`uv build`, the wheel installed into a clean venv, `cjdev --help` run, and
`dist/` uploaded as an artifact). `uv sync --locked` in every job: a stale `uv.lock`
is a CI failure, not a surprise later. `setup-uv` is pinned to an exact version,
because no rolling tag exists and an unpinned action name floats (issue #8).

## Consequences

The hooks stay the primary gate and CI the enforcing one; a PR is green by the same
commands a contributor runs locally. Releases are deliberately not here: a merge into
`master` releasing by itself is issue #23, still open.
