# ADR-0039: Scratch is moved into the worktree for the build, not symlinked out of it

Status: accepted, 2026-10-08. Closes #39. Supersedes, in part, ADR-0017: its symlink redirect.

## Context

ADR-0017 kept build output out of the worktree with a relative symlink at each scratch
path. Upstream scripts assume a real directory there, and one container build of the SDK
broke on six paths in four units, two ways:

- **Wipe.** The script deletes the directory and recreates it. `rmtree` refuses a symlink,
  and `rm -r` removes the link so `mkdir` puts a real directory in its place: runtime's
  `CMakebuild` and `build/cjthread_build`, cjpm's `cpp/out`.
- **Walk-up.** The script reaches the source tree with `..` from its build directory,
  which from inside a link resolves under `.cjdev/build`: stdlib's `../../cmake`, stdx's
  `../../build/common`, cjpm's `cmake ..`.

Dropping wiped paths from `scratch` and planting links for each walk-up made every new
upstream script a manual fix.

## Decision

**A unit's scratch directories live in `.cjdev/build/<set>/<env>/<profile>/<unit>/` and
are renamed into the worktree before it builds and back after**, whether the build passed
or failed. The script sees real directories at the paths it expects. A rename is free on
one filesystem, and the worktree and `.cjdev` share a root, so the profile key survives:
switching profiles costs no rebuild.

**A marker beside the build lock names the profile whose scratch is in the worktree.** It
is written before anything moves in and removed after everything moves out. A run killed
in between leaves it, and the next run moves that profile's scratch back before its own
moves in. A real directory with no marker is still a refusal. A symlink that resolves
under `.cjdev/build` is an old redirect, and it is removed together with its target: cmake
configured that directory through the link, recorded its path under `.cjdev/build`, and
keeps writing there from the worktree.

Rejected: building in tree (loses the profile key), bind mounts in the container (fix
walk-up only, and only in one environment), cjdev-planted walk-up links (per-script
guesswork), a worktree per profile (uncommitted edits are not shared), and an upstream
build-dir flag (four repositories, and a stopgap needed anyway).

## Consequences

The wiped paths are scratch again. A workspace built under the symlinks rebuilds each unit
once, from ccache where the compiler is concerned, and a wiped path upstream recreated as
a real directory in the worktree is removed by hand once. A script that writes to its
scratch's home path during the build makes the move out a refusal rather than a merge.
Ctrl-C reaches the build in
its own process group and the move out waits for it to exit; only a killed cjdev leaves
scratch in the worktree, and `info/exclude` keeps that state clean to git until the next
run.
