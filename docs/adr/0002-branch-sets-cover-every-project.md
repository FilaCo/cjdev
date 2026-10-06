# ADR-0002: A branch set covers every project, created by one command

Status: accepted, 2026-09-16. Closes #2.

## Context

Work on the Cangjie SDK is work on several repositories at once: a compiler change is
tested against the runtime, the stdlib and the tools on top of them. Doing that by hand
means creating the same branch in each repository, checking each one out somewhere, and
keeping the set straight for the length of the task.

## Decision

A **branch set** is one checkout per project, all on a branch of the same name, gathered
under a single directory named after the branch: `cjdev branch new fix/parser-ice`
creates `fix-parser-ice/` holding one checkout of every project the workspace holds.

- The set covers **every** project, not the ones the change is expected to touch: a
  change that turns out to reach further than expected finds its branch already there.
- Each checkout starts from the project's **recorded upstream default branch**, never
  an assumed `main`.
- A branch that already carries the name is **adopted** rather than failed, and a set
  that covers only some projects is completed, so an interrupted task resumes.
- Every refusal happens in `decide`, before the first worktree exists: `git worktree
  add -b` creates the branch before it attempts the checkout, so a mid-flight failure
  would leave branches behind that nothing cleans up. A name that cannot be a git
  branch, a directory held by another branch set, a name already checked out in another
  set (git allows one worktree per branch) — all are named before anything runs.

## Consequences

Several branch sets coexist, so an interrupted task is left where it stands and
returned to later. The branch name flattens into the directory name
(`fix/parser-ice` → `fix-parser-ice`), predictable without consulting the tool.
