# cjdev — requirements

Status: **draft**. Written before implementation; every open question in
[§10](#10-open-questions) must be answered before the corresponding requirement is
considered frozen.

Requirement IDs are stable. Refer to them from issues, commits and PRs.

Priorities follow RFC 2119: **MUST** (v1.0 blocker), **SHOULD** (v1.0 target, may slip),
**MAY** (nice to have, explicitly out of the first milestones).

---

## 1. Purpose

Working on the Cangjie SDK means juggling several independent git repositories that are
built, tested and released together. Day-to-day that costs:

- N× `git checkout` / `git rebase` / `git push` for one logical change;
- full rebuilds after every branch switch;
- hand-written `build.py` invocations in the right order with the right flags;
- an ad-hoc container or a polluted host toolchain, depending on the day;
- N× manual PR creation on gitcode plus a tracking issue filled in by hand.

`cjdev` is a **workflow orchestrator** for that set of repositories. It owns branch
topology, build ordering, environment isolation and forge interaction. It does **not**
own build logic — that stays upstream.

## 2. Glossary

| Term | Meaning |
| --- | --- |
| **component** | One Cangjie SDK git repository (`cangjie_compiler`, `cangjie_runtime`, …). |
| **upstream** | The canonical repository under the `Cangjie` organisation on gitcode. |
| **origin / fork** | The user's personal fork of a component. |
| **workspace** | A `cjdev`-managed directory tree holding object stores, worktrees, build outputs and caches for the whole component set. |
| **branch set** | A named, cross-component branch identity: the same branch name checked out in every component that participates in it. The unit `cjdev` switches, builds, tests and ships. |
| **manifest** | Versioned description of the component set: URLs, default branches, build recipes, dependency edges. |
| **lock** | Per-workspace record of the exact commit each component is pinned to for a given branch set. |
| **executor** | The mechanism used to run an external command: on the host, or inside a docker/podman container. |
| **forge** | The hosting platform (gitcode; possibly others later) providing PRs, issues and tokens. |

## 3. Non-goals

- **Reimplementing upstream builds.** `cjdev` invokes each component's own build entry
  point. If a build flag changes upstream, `cjdev` passes it through; it does not model it.
- **Being a package manager for Cangjie programs.** This is a tool for people who build
  the SDK, not for people who consume it.
- **Being a CI system.** `cjdev` should be *callable* from CI and produce
  machine-readable output, but it does not schedule, queue or report.
- **Supporting arbitrary repositories.** The manifest is Cangjie-shaped. Genericity is a
  side effect, never a requirement.
- **Mandating AI.** Every AI-assisted feature is opt-in, and the tool is fully usable with
  no model, no key and no network beyond git.

## 4. Domain model

### 4.1 Workspace layout

```
<workspace-root>/
  cjdev.toml                      # workspace config (versioned by the user, optional)
  cjdev.lock                      # resolved commit per component per branch set
  repos/
    cangjie_compiler.git/         # single object store per component (bare)
    cangjie_runtime.git/          # remotes: upstream (read-only), origin (fork)
    ...
  trees/<branch-set>/
    cangjie_compiler/             # git worktree
    cangjie_runtime/
    ...
  build/<branch-set>/<profile>/   # out-of-tree build dirs, one per component
  dist/<branch-set>/<profile>/    # assembled/installed SDK
  cache/
    ccache/                       # shared across ALL branch sets — the point of the design
    misc/
  log/<branch-set>/               # per-run command logs
```

Rationale: one object store per component (disk + fetch cost paid once), one worktree per
branch set (switching is instant and does not invalidate anyone's build dir), one build dir
per branch set × profile (no cross-branch clobbering), **one shared compiler cache**
(cross-branch reuse).

### 4.2 Branch sets

A logical change rarely touches every component. Therefore:

- A branch set is identified by a **name** (e.g. `fix/parser-ice-1234`).
- For each component, the branch set resolves to either the branch of that name (if it
  exists) or a **base ref** — that component's default branch, pinned to a commit in
  `cjdev.lock`.
- Components are enrolled into a branch set **lazily**: a component gets a real branch the
  first time it is modified, or on explicit `cjdev branch add <component>`.
- `cjdev.lock` always records the resolved commit for every component, so a branch set is
  reproducible and `cjdev` always knows which components actually diverged (input to build
  selection, PR creation and issue text).

---

## 5. Functional requirements

Traceability to the original request: BRANCH←(1), BUILD←(2), CACHE←(3), ENV←(4),
TEST←(5), FORGE←(6), SYNC←(7).

### 5.1 BRANCH — synchronous multi-repository branching

| ID | Priority | Requirement |
| --- | --- | --- |
| BRANCH-1 | MUST | Create a branch set across all components with one command; the branch name is identical in every participating fork. |
| BRANCH-2 | MUST | Switch to a branch set with one command; every component ends up on the corresponding branch or its pinned base ref. |
| BRANCH-3 | MUST | Branch sets are backed by `git worktree`, so switching never rewrites an existing checkout and never invalidates another branch set's build directory. |
| BRANCH-4 | MUST | List branch sets with, per component, the branch, the short SHA, the dirty flag and the ahead/behind counts vs `origin` and `upstream`. |
| BRANCH-5 | MUST | Delete a branch set: remove worktrees, optionally its build/dist directories, optionally the remote branches; refuse when a worktree is dirty unless forced. |
| BRANCH-6 | SHOULD | Enrol a component into an existing branch set lazily, branching from the pinned base ref rather than from whatever `upstream` looks like today. |
| BRANCH-7 | SHOULD | Operate on a subset via `--only`, `--exclude` and named component groups from the manifest. |
| BRANCH-8 | SHOULD | Refuse partially-applied state: preflight every component, and on failure report exactly which components changed and how to resume. |
| BRANCH-9 | MAY | Import an existing manual checkout into a workspace instead of re-cloning. |

Sketch:

```
cjdev branch new fix/parser-ice --from upstream/default
cjdev branch switch fix/parser-ice
cjdev branch list
cjdev branch rm fix/parser-ice --remote --build
```

### 5.2 SYNC — keeping local, fork and upstream aligned

The reference procedure, per component:

```
git fetch upstream <default>
git branch -f <default> upstream/<default>       # no checkout: the worktree is untouched
git push --force-with-lease origin <default>     # optional, --fork
git rebase <default> <branch-set-branch>         # in the branch set's worktree
git push --force-with-lease origin <branch>      # optional, --push
```

| ID | Priority | Requirement |
| --- | --- | --- |
| SYNC-1 | MUST | One command fetches `upstream` and fast-forwards the local default branch for every component. |
| SYNC-2 | MUST | Updating the default branch MUST NOT check it out. Move the ref directly (`git branch -f`) so no worktree is touched and no rebuild is triggered. This replaces the `checkout` / `checkout -` dance. |
| SYNC-3 | MUST | Rebasing the current branch set onto the refreshed default branch is a distinct, explicitly-requested step. |
| SYNC-4 | MUST | Pushing to the fork is opt-in via a flag (`--fork` for default branches, `--push` for branch-set branches), never implicit. |
| SYNC-5 | MUST | All force pushes use `--force-with-lease`. Plain `-f` is never issued. |
| SYNC-6 | MUST | Before any history rewrite, save a backup ref (`refs/cjdev/backup/<branch>/<utc-timestamp>`) and print how to restore it. |
| SYNC-7 | MUST | Refuse to rebase a dirty worktree; `--autostash` opts into stashing. |
| SYNC-8 | MUST | The default branch name is detected per component (`refs/remotes/upstream/HEAD`), overridable in the manifest. Never hardcode `master`/`main`/`dev`. |
| SYNC-9 | MUST | On conflict, stop, report which components are done / conflicted / untouched, and support `cjdev sync --continue` and `cjdev sync --abort`. |
| SYNC-10 | SHOULD | Enable `rerere` inside the workspace so the same conflict resolved in one branch set replays in the next. |
| SYNC-11 | SHOULD | `--dry-run` prints the exact git commands for every component without running any. |
| SYNC-12 | SHOULD | Detect and refuse the "upstream rewrote history" case rather than producing a silently wrong rebase. |

Sketch:

```
cjdev sync                          # fetch + ff default branches everywhere
cjdev sync --fork                   # ...and force-with-lease push them to the fork
cjdev sync --rebase                 # ...and rebase the active branch set on top
cjdev sync --rebase --push          # ...and publish the rebased branches
cjdev sync --only cangjie_compiler --dry-run
```

### 5.3 BUILD — building the SDK, whole or in parts

| ID | Priority | Requirement |
| --- | --- | --- |
| BUILD-1 | MUST | Build the whole SDK for the active branch set with one command, in dependency order derived from the manifest graph. |
| BUILD-2 | MUST | Build a single component, with `--only`, `--from <c>` (component and dependents), `--upto <c>` (component and dependencies). |
| BUILD-3 | MUST | Build recipes are declarative manifest entries that invoke each component's own build entry point. `cjdev` never reimplements or forks upstream build logic. |
| BUILD-4 | MUST | Extra arguments pass through verbatim to the underlying build script (`cjdev build cangjie_compiler -- --foo`). |
| BUILD-5 | MUST | Build outputs live outside the source tree, keyed by branch set and profile; two branch sets never share a build directory. |
| BUILD-6 | MUST | Named profiles (`debug`, `release`, …) defined in the manifest and overridable per workspace. |
| BUILD-7 | SHOULD | Skip components whose inputs are unchanged, using a stamp keyed on commit + dirty-tree hash + resolved build flags + toolchain identity; `--force` rebuilds anyway. |
| BUILD-8 | SHOULD | Fail fast by default, `--keep-going` to build everything buildable and report a summary. |
| BUILD-9 | SHOULD | Emit a per-component timing and cache-hit summary at the end of a build. |
| BUILD-10 | SHOULD | Assemble a usable SDK into `dist/<branch-set>/<profile>` and print how to put it on `PATH`. |
| BUILD-11 | MAY | Parallel builds of independent graph nodes. |
| BUILD-12 | MAY | Cross-target builds (see [§10](#10-open-questions)). |

### 5.4 CACHE — incrementality across branches

| ID | Priority | Requirement |
| --- | --- | --- |
| CACHE-1 | MUST | A single `ccache` store is shared by every branch set and every environment mode. |
| CACHE-2 | MUST | The cache is configured so that objects hit **across worktrees**, i.e. despite differing absolute source paths. In practice: `CCACHE_BASEDIR` at the workspace root plus `hash_dir = false`. Without this the shared cache is nearly useless — different worktree paths defeat it. |
| CACHE-3 | MUST | The cache is mounted into containers at the same path used on the host, so host and container builds share hits. |
| CACHE-4 | SHOULD | `cjdev cache stats` / `cjdev cache clear`, plus a size limit configured at workspace creation. |
| CACHE-5 | SHOULD | Document explicitly which parts of the build ccache does **not** accelerate (see [§9](#9-risks)), so the incrementality promise is not oversold. |
| CACHE-6 | MAY | Pluggable backend (`sccache`) behind the same interface. |
| CACHE-7 | MAY | `cjdev gc` to prune build/dist directories of stale branch sets by age or total size. |

### 5.5 ENV — host and containerised environments

| ID | Priority | Requirement |
| --- | --- | --- |
| ENV-1 | MUST | Every external command runs through a single **executor** abstraction. No command path bypasses it. |
| ENV-2 | MUST | Two executors: `host` and `container`. Container has first-class **docker** and **podman** backends; the difference is confined to the backend, never leaked into commands. |
| ENV-3 | MUST | Auto-detect the available runtime; overridable by config, `CJDEV_ENV`, and a per-invocation flag. |
| ENV-4 | MUST | Files produced inside a container are owned by the invoking user on the host (docker: `--user`; podman rootless: `--userns=keep-id`). Root-owned build artifacts are a defect. |
| ENV-5 | MUST | The workspace is mounted at a **fixed path** inside the container, identical across runs and images, so cache keys and debug paths stay stable. |
| ENV-6 | MUST | SELinux-labelled mounts (`:z`) where required, without breaking non-SELinux hosts. |
| ENV-7 | MUST | Ship a `Containerfile` buildable by both runtimes; `cjdev env build` builds it, `cjdev env pull` fetches a published one. |
| ENV-8 | MUST | The image reference (by digest) used for a build is recorded alongside the build stamp, so a toolchain change invalidates the stamp. |
| ENV-9 | SHOULD | `cjdev env shell` drops into the configured environment with the same mounts and env vars a build would use. |
| ENV-10 | SHOULD | `cjdev env doctor` verifies prerequisites for the selected mode (runtime present, image available, cgroups/userns sane, disk space, host toolchain versions). |
| ENV-11 | SHOULD | Same command, same result: switching between host and container mode must not require editing any config or path. |
| ENV-12 | MAY | Long-lived container reuse (`exec` into a running container) instead of one container per command, if start-up cost proves material. |

### 5.6 TEST — running the Cangjie test framework

| ID | Priority | Requirement |
| --- | --- | --- |
| TEST-1 | MUST | Run `cangjie_test_framework.py` against the SDK built for the active branch set, with the environment wired up automatically. |
| TEST-2 | MUST | Raw arguments pass through verbatim (`cjdev test -- --any-upstream-flag`). Shortcuts never block the underlying tool. |
| TEST-3 | MUST | Named **presets** (framework flags + suite selection + environment) resolved in layers: built-in → manifest → workspace config → user config → CLI flags. |
| TEST-4 | MUST | Select suites/subsets by short name or path, with tab-completable names. |
| TEST-5 | SHOULD | `cjdev test list` shows available presets and suites with their origin layer. |
| TEST-6 | SHOULD | Machine-readable results (`--json`) plus a stable non-zero exit code on failure, for CI use. |
| TEST-7 | SHOULD | `--rerun-failed` replays the previous run's failures. |
| TEST-8 | SHOULD | Build the SDK first if it is stale, unless `--no-build`. |
| TEST-9 | MAY | Compare a run against a stored baseline and report only new failures. |

### 5.7 FORGE — gitcode from the terminal

| ID | Priority | Requirement |
| --- | --- | --- |
| FORGE-1 | MUST | A `forge` port with a gitcode adapter; no gitcode specifics leak into command or domain code. |
| FORGE-2 | MUST | Token from environment or the OS keyring; never written to a versioned file; never printed, including in verbose logs and error output. |
| FORGE-3 | MUST | Open PRs for **exactly the components that diverged** in the active branch set, in one command, using the branch-set name as the source branch. |
| FORGE-4 | MUST | Cross-link the PRs of one branch set: each body lists its siblings and the tracking issue. |
| FORGE-5 | MUST | Preview the full PR title/body per component and require confirmation before anything is created; `--yes` for scripted use. |
| FORGE-6 | MUST | Idempotent: re-running updates the existing PRs rather than creating duplicates. |
| FORGE-7 | SHOULD | Create the tracking issue in `cangjie_compiler` from the repository's issue template, pre-filled from branch-set metadata and the commit range. |
| FORGE-8 | SHOULD | Optional AI-assisted drafting of the issue/PR body from the diff: opt-in flag, delegated to a user-configured external command, output always opened in `$EDITOR` before submission. Never auto-posted. |
| FORGE-9 | SHOULD | `cjdev pr status` shows CI state, review state and merge state for every PR in the branch set. |
| FORGE-10 | SHOULD | Respect a documented ordering when the component PRs depend on each other, and say so in the bodies. |
| FORGE-11 | MAY | Fork creation and remote wiring for a component the user has not forked yet. |
| FORGE-12 | MAY | A second adapter (e.g. GitHub) to prove the port is real. |

**Confidentiality constraint on FORGE-8:** the diff of an unpublished change is sent to
whatever command the user configures. The tool must state this at the point of use and
default to off.

### 5.8 CFG — configuration and manifest

| ID | Priority | Requirement |
| --- | --- | --- |
| CFG-1 | MUST | Layered configuration: built-in defaults → user config → workspace config → `CJDEV_*` env → CLI flags, later wins. |
| CFG-2 | MUST | The component manifest (URLs, default branches, groups, dependency edges, build recipes, profiles) ships with `cjdev` and is overridable per workspace. |
| CFG-3 | MUST | The manifest carries a schema version and `cjdev` refuses a version it does not understand, with an actionable message. |
| CFG-4 | MUST | `cjdev status` reports workspace root, active branch set, per-component branch/SHA/dirty/ahead-behind, environment mode, cache stats and build freshness. |
| CFG-5 | SHOULD | `cjdev config show --origin` prints the effective config annotated with the layer each value came from. |
| CFG-6 | SHOULD | Everything `cjdev` owns lives under the workspace root and is removable with `rm -rf`; no hidden global state beyond the user config file. |

### 5.9 UX — cross-cutting behaviour

| ID | Priority | Requirement |
| --- | --- | --- |
| UX-1 | MUST | `--dry-run` on every mutating command, printing the exact external commands that would run. |
| UX-2 | MUST | Destructive actions (history rewrite, force push, worktree/branch deletion, cache clear) confirm interactively; `--yes` for automation; never destructive by default. |
| UX-3 | MUST | Every external invocation is logged with its full argv, cwd and exit status; `-v` echoes it live. |
| UX-4 | MUST | On failure, report the failing component, the command, and the tail of its output — never a bare traceback. |
| UX-5 | MUST | Exit codes are meaningful and documented (0 ok, 1 operation failed, 2 usage error, 3 preconditions unmet). |
| UX-6 | SHOULD | `--json` output for the reporting commands (`status`, `branch list`, `test`, `pr status`). |
| UX-7 | SHOULD | Shell completion for fish, bash and zsh, including dynamic completion of branch sets, components, presets. |
| UX-8 | SHOULD | Multi-component operations run with a stable, non-interleaved progress display and a final summary table. |
| UX-9 | SHOULD | Interrupting (`Ctrl-C`) leaves the workspace in a resumable state, never a half-rewritten one. |

---

## 6. Non-functional requirements

| ID | Priority | Requirement |
| --- | --- | --- |
| NFR-1 | MUST | Python ≥ 3.10, thin runtime dependency set. No dependency is added for a feature that shells out anyway. |
| NFR-2 | MUST | Domain and application layers are testable without git, network, containers or a forge account. Adapters are the only place that touches the outside world. |
| NFR-3 | MUST | Git is driven via the `git` CLI (worktrees, rerere, force-with-lease and credential helpers all behave as documented), not a reimplementation. |
| NFR-4 | MUST | Linux is the supported platform for v1.0. macOS is best-effort; nothing may be gratuitously Linux-only in the domain layer. |
| NFR-5 | SHOULD | `cjdev status` on a warm workspace completes in well under a second — it is going to be run constantly, possibly from a prompt. |
| NFR-6 | SHOULD | Branch-set switching is O(worktree checkout) and does not touch build directories. |
| NFR-7 | SHOULD | The tool is usable offline for everything that does not inherently need the network. |

## 7. Architecture decisions

These are the decisions the requirements above imply. Recorded here until they graduate
into proper ADRs.

1. **Bare object store + worktrees, not N clones.** One fetch, one object store, instant
   branch-set switching, independent build dirs. This is the structural precondition for
   both BRANCH and CACHE.
2. **Executor port from day one.** Host vs. container is not a feature to bolt on later —
   retrofitting it means rewriting every command. Every subprocess goes through the port
   from the first commit.
3. **`cjdev` orchestrates, upstream builds.** Build recipes are declarative descriptions of
   how to call someone else's script. The moment `cjdev` contains compiler build knowledge
   it starts drifting from upstream.
4. **The lock file is the source of truth for "what is this branch set".** It makes builds
   reproducible, tells PR creation which components diverged, and makes `status` cheap.
5. **Forge behind a port.** Partly for testability, partly because the gitcode API surface
   is the least certain part of this design (see [§10](#10-open-questions)) and must be
   replaceable without touching command code.
6. **Layering (ports & adapters).**
   - `domain/` — `Workspace`, `Component`, `BranchSet`, `BuildGraph`, `Profile`. Pure, no I/O.
   - `application/` — one use case per command, orchestration and policy only.
   - `infra/` — `GitAdapter`, `HostExecutor`, `ContainerExecutor`, `CcacheAdapter`, `GitcodeForge`.
   - `commands/` — Typer wiring, argument parsing, rendering. Thin by construction.
7. **AI is a delegate, never a dependency.** Drafting an issue means handing a prompt to a
   command the user configured. `cjdev` gains no model SDK, no API key handling, and no
   behaviour that breaks when offline.

## 8. Milestones

| Milestone | Contents | Rationale |
| --- | --- | --- |
| **M1 — workspace & git** | CFG-1..4, BRANCH-1..5, SYNC-1..9, UX-1..5 | The daily pain is branch juggling, and this milestone alone is already worth using. |
| **M2 — build & cache** | BUILD-1..6, CACHE-1..3, executor (host only) | Delivers the incrementality promise. |
| **M3 — containers** | ENV-1..10 | Slots into M2's executor port with no command changes — that is the test of decision 2. |
| **M4 — test** | TEST-1..6 | Depends on a working build. |
| **M5 — forge** | FORGE-1..7, FORGE-9 | Needs branch sets and the lock to know what to publish. |
| **M6 — polish** | FORGE-8, BUILD-7..10, UX-6..9, completions | Everything that is a multiplier rather than a capability. |

## 9. Risks

| # | Risk | Mitigation |
| --- | --- | --- |
| R1 | **ccache only covers C/C++.** Cangjie-language parts of the SDK are compiled by `cjc` and get nothing from ccache; their incrementality depends entirely on the upstream build system. The cross-branch reuse promise (CACHE) is therefore partial. | Measure before promising. Document the split (CACHE-5). Investigate whether the Cangjie-side build has a usable cache of its own. |
| R2 | **CMake reconfiguration per worktree** can eat the savings ccache produces. | Measure. Consider a per-branch-set persistent configure step, or a shared configure cache. |
| R3 | **Absolute paths defeat the shared cache.** Different worktree path ⇒ different hash ⇒ zero hits. | CACHE-2 (`CCACHE_BASEDIR` + `hash_dir = false`) and ENV-5 (fixed container path) are not optional details; they are the feature. |
| R4 | **Disk growth.** Branch sets × profiles × build dirs is measured in tens of GB. | CACHE-7 (`gc`), size reporting in `status`, opt-in build-dir removal on branch-set deletion. |
| R5 | **Force-push data loss.** SYNC rewrites published history by design. | `--force-with-lease` only (SYNC-5), backup refs (SYNC-6), confirmation (UX-2), `--dry-run` (SYNC-11). |
| R6 | **gitcode API uncertainty.** Auth flow, PR endpoints and rate limits are not yet verified. | Spike before M5; forge port (decision 5) contains the blast radius. |
| R7 | **Upstream build scripts change.** Flags and entry points move. | Recipes are data, not code (BUILD-3); pass-through args (BUILD-4); pin the manifest schema (CFG-3). |
| R8 | **Submodules / LFS in a worktree** behave differently from a plain clone. | Verify per component during M1; if present, handle explicitly rather than by accident. |
| R9 | **Partial cross-repo operations.** A failure mid-way leaves components inconsistent. | Preflight everything (BRANCH-8), resumable `--continue`/`--abort` (SYNC-9), never a silent partial success. |
| R10 | **Scope.** Seven feature areas is a lot for one tool. | Milestones are ordered so each is independently useful; M1 ships before M2 starts. |

## 10. Open questions

Each of these blocks a requirement. Answers should be folded back into this document.

1. **Component set.** Exact repository list, their gitcode URLs, and each one's default
   branch name. Blocks: the manifest, all of BRANCH and SYNC.
2. **Dependency graph.** The real build order and which edges are hard vs. incidental.
   Blocks: BUILD-1/2.
3. **Build entry points.** Per component: script, required flags, where outputs land, and
   whether out-of-tree builds are supported at all. Blocks: BUILD-3/5.
4. **`cangjie_test_framework.py`.** Which repository owns it, how it locates an SDK, what
   its suite/preset vocabulary is. Blocks: all of TEST.
5. **gitcode API.** Base URL, auth (PAT? OAuth?), PR and issue endpoints, rate limits, and
   whether an official CLI exists worth wrapping instead. Blocks: all of FORGE.
6. **Targets.** Is cross-compilation in scope for v1.0 (aarch64, Windows, OpenHarmony), or
   host-only? Blocks: BUILD-12, profile design.
7. **Base image.** Which distro and toolchain versions does an SDK build actually require,
   and is there a published image already? Blocks: ENV-7.
8. **Issue template.** The template in `cangjie_compiler` — its fields and which of them
   can be derived mechanically rather than by an LLM. Blocks: FORGE-7/8.
9. **Multi-repo PR conventions.** Does the Cangjie project have an existing convention for
   linking PRs across repositories that `cjdev` should follow rather than invent? Blocks:
   FORGE-4/10.
