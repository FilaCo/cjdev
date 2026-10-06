# ADR-0009: Every change starts with an issue, and the PR closes it

Status: accepted, 2026-09-10. Closes #9.

## Context

PR #6 was opened against issue #5 and closed it on merge; the follow-up fix (the
setup-uv pin) then had no issue to live in and had to be requested out of band, with
issue #8 created only after the fact. Nothing in the repo stated the expected order, so
every contributor or automation would rediscover it the same way.

## Decision

Issue first, always — even a follow-up fix to something that just merged. The issue
keeps the *why* (context, functional requirements, rejected alternatives); the pull
request keeps the *how* and links the pair with a closing keyword (`Fixes #N`), so the
merge closes the issue automatically. The PR template carries the empty `Fixes #` and
a checklist mirroring `pre-push`, which turns the convention into the path of least
resistance.

## Consequences

The issue thread is where the requirements and the rejected alternatives remain
findable after the PR is squash-merged into a single commit. ADR numbering builds on
this (ADR-0024): a decision's number is its issue's, allocated when the issue is
created rather than when the PR lands.
