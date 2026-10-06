# ADR-0017: Builds happen out of tree, and the worktree carries the state

Status: accepted, 2026-09-18. Closes #17.

## Context

`cjdev build` had no code. The build graph was finished (`Manifest.build_order()`),
the paths declared but dead, and everything touching the outside world unanswered.
Every upstream `build.py` derives its output directory from `__file__` and takes no
flag for it — so the only way out of the worktree is a redirect the worktree cannot
refuse. Three things genuinely differ per unit and cannot be constants in code: which
directories are scratch, how the build is invoked, how the install is invoked.

## Decision

**Per-unit build data is manifest data** (`schema_version = 2`): `scratch`,
`build`, `install` per unit, with literal token substitution of `{profile}`,
`{jobs}`, `{dist}`, `{build_dir}` and nothing else — no conditionals; the moment a
template needs an `if`, the manifest has become a programming language and the logic
belongs in code. This is the existing rule applied: if you are about to write the
same command shape N times, the N belongs in data. (The per-unit vocabularies really
do differ: `-t` is a `BuildType` enum for the compiler and the stdlib, a free string
for cjpm.)

**Scratch directories are redirected out of the worktree by relative symlinks** into
`.cjdev/build/<branch set>/<profile>/<unit>/`, because the scratch set is per unit:
`build/` is *tracked source* in `cangjie_runtime/runtime` and `cangjie_stdx`, so a
uniform `build` redirect would delete those projects' cmake toolchains. The links are
relative so they resolve at any mount point — what the container executor mounts the
workspace at a different absolute path. A real directory where a link belongs is a
refusal, not a silent delete of somebody's artefacts.

**A worktree therefore has a profile.** Links are verified before every build and
repointed atomically, all of a unit's together, under an flock per (branch set, build
unit). The paths are excluded via the object store's `info/exclude` — every worktree
of that store shares it, one write covers every branch set, and no tracked file is
touched. cjdev owns removing them: upstream `clean` calls `rmtree` on what is now a
symlink and raises; there is no cjdev command for it yet (architecture.md, *Questions,
answers and consent*, names the missing-name problem).

**Output is teed** to `.cjdev/log/<branch set>/<unit>.log` while the build runs, so a
long build can be tailed; every unit installs into one shared
`.cjdev/dist/<branch set>/<profile>`, and each unit builds *with* what the ones before
it installed — the same environment `source <sdk>/envsetup.sh` would set up, so
nothing is sourced by hand.

## Consequences

Two branch sets never share a build; switching profiles costs no reconfigure; ccache
is shared across branch sets (it hashes the compiler binary, so entries coexist rather
than collide). The environment later became a key beside the profile in these paths
(ADR-0021). Builds run one unit at a time — each upstream script already takes the
whole machine.
