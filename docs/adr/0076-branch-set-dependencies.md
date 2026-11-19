# ADR-0076: A branch set can select its own third-party sources

Status: accepted, 2026-11-19. Closes #76.

## Context

One compiler task may need upstream LLVM while another must build with a pinned
fork. Both use the same workspace manifest and commit cache.

## Decision

Store the requested ref and optional upstream in the branch set's record, keyed by
build unit and dependency. The build overlays these fields on the workspace's
declaration. A moving ref keeps the resolution behavior of ADR-0027. The link
continues to identify the commit actually available in the worktree.

## Consequences

A user can inspect or change a selection offline. Builds record which upstream
and ref produced a linked commit so an offline rebuild can reuse it safely after
a selection changes. Removing a selection restores inheritance. Source trees stay
shared by commit, including when two tasks select it through different refs.
