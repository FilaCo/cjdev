# ADR-0031: Scratch that drifted from the manifest is reconciled, not refused

Status: accepted, 2026-10-12. Closes #31. Supersedes, in part, ADR-0039: its refusal of a real directory with no marker.

## Context

Two states left a by-hand `rm` in a worktree as the only way forward. A scratch path
held a real directory no cjdev build left there, after an upstream script rewrote it,
and the build refused. And a manifest that dropped a scratch path (#30 dropped
`CMakebuild` before ADR-0039 restored it) left the old redirect symlink behind, which
nothing in cjdev looked at any more. Both are cjdev's own layout drifting from the
manifest, so every manifest change became a manual migration of every workspace.

## Decision

**A real directory with no marker is absorbed as the scratch of the profile being
built.** It moves to that profile's home under `.cjdev/build` and comes back in with
the rest. Whatever already lived at that home is removed: the worktree's copy was
written after cjdev last moved that scratch out, and `.cjdev/build` is cjdev's own.

**A symlink into `.cjdev/build` at a path that is no longer scratch is removed.** The
candidates come from the store's `info/exclude`: every redirect cjdev wrote was
excluded there too, and nothing prunes it, so it remembers what the manifest forgot.
The link goes, its target stays (nothing reads it). A symlink pointing anywhere else is
not cjdev's and is left alone.

Both are tree mutations through `FileSystem`, which now reports each one to the
progress display and the workspace log.

Rejected: keeping the refusal with a better remedy (still a manual migration), and
scanning the worktree for links (a full walk of an SDK checkout on every build).

## Consequences

Somebody's hand-built artefacts at a scratch path become cjdev's: the next build
uses them and moves them out, and a previous cjdev build of that profile there is
lost. Leftovers under `.cjdev/build` from a dropped path stay until removed by hand.
