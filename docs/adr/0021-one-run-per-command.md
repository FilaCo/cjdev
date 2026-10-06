# ADR-0021: One docker run --rm per command, and the environment is a workspace property

Status: accepted, 2026-09-20. Closes #21. Supersedes, in part, this issue's own FR-2.

## Context

The README promised containerised builds and nothing in the tree did it. The
groundwork was laid on purpose: `Executor` is a port because its second
implementation is the container one, and the scratch symlinks are relative
(ADR-0017) so they resolve at any mount point. What the issue proposed included one
**long-lived container per workspace**, commands run through `exec`, named from the
workspace root, started lazily.

## Decision

**One `docker run --rm` per command, and no long-lived container.** The unit of work
is a build unit — tens of minutes of compiling — so container creation is noise
against it. What a per-command run buys: no name to derive, no staleness to check,
nothing to reclaim but the image, and a cancellation that works — the client proxies
the signal to pid 1, `--init` gives it a pid 1 that forwards, and `--rm` reaps what
is left. Nothing may `SIGKILL` that client, because a killed client leaves a live
container behind. This revises the issue's FR-2 in flight: the lifecycle of a
long-lived container (reclamation, staleness, naming) proved to be machinery the
per-command run makes unnecessary. (In container mode the environment *does* serve
`env shell` as a foreground interactive command.)

**The environment is a workspace property, answered once at `cjdev init`** and kept
in `.cjdev/config.toml` as a section that is *not* a manifest override:
`mode = "host" | "container"`, `runtime = "docker" | "podman"`. Host is the default
and a missing section means host — every workspace that predates this keeps building
exactly as before. The environment becomes a key in the build and dist paths beside
the profile: two environments are two targets from two toolchains, and one `bin/cjc`
cannot be both.

**The image ships as a Dockerfile in the wheel**, reached through
`importlib.resources` like the manifest, and its tag carries the file's content hash —
a cjdev upgrade that changes the recipe is a new tag rather than a stale image nobody
notices. The two runtimes' deltas are data (`infra/container.py`), not one argv with
the program name swapped: rootful docker runs as root and needs `--user` for what it
writes to belong to the caller; rootless podman maps the caller onto root already, so
`--user` would break it — `--userns=keep-id` instead.

**The image describes itself, and nothing probes it from the inside.** `info` and
`image inspect` are host-side reads, so `--dry-run` may make them and plan from the
truth. `ContainerExecutor` is outermost, not innermost: everything below it — dry
run, the step label, `-v`, the workspace log — sees the argv that will really run.

**Only `build` crosses the boundary.** git stays on the host, all of it: credential
helpers, the ssh agent, the worktree registrations are this machine's, and `cjdev
status` must not start failing because a daemon is down. The build's own git runs
inside (cjpm's build clones libuv), which is why the image carries git and CA
certificates.

## Consequences

A workspace that predates the environment key gets a fresh tree on its first
container build — the scratch symlinks are repointed and both trees kept, nothing
reclaims the old one; the same trade switching profiles has always made. `cjdev env
run` replays any recorded command with the same mount, cwd and variables, in host
mode too, which makes the executor's argv honest: what the journal recorded is what
can be run again.
