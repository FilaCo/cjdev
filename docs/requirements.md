# cjdev - requirements

Status: **draft**. Written before implementation. The project set, targets, forge
client and environment baseline were settled on 2026-09-03 ([§10.1](#101-resolved)); the
questions remaining in [§10.2](#102-still-open) still block the requirements they name.
Parallel execution ([§5.10](#510-par--parallel-execution)) was added on 2026-09-04.
The machine-facing half of [§5.9](#59-ux--cross-cutting-behaviour) (UX-6, UX-11..18) was
added on 2026-09-07.

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
own build logic - that stays upstream.

## 2. Glossary

| Term | Meaning |
| --- | --- |
| **project** | One Cangjie SDK git repository (`cangjie_compiler`, `cangjie_runtime`, …). The unit of cloning, branching and PR creation. |
| **build unit** | One buildable subproject inside a project (`runtime`, `stdlib`, `cjpm`). The unit of the dependency graph and of build directories; a project may hold several. Named flat and uniquely across the manifest, because the name is the token `cjdev build <unit>` takes; which project holds it is recorded separately. |
| **upstream** | The canonical repository under the `Cangjie` organisation on gitcode. |
| **origin / fork** | The user's personal fork of a project. |
| **workspace** | A `cjdev`-managed directory tree holding object stores, worktrees, build outputs and caches for the whole project set. |
| **branch set** | A named, cross-project branch identity: the same branch name checked out in every project that participates in it. The unit `cjdev` switches, builds, tests and ships. |
| **manifest** | Versioned description of the project set: URLs, default branches, build recipes, dependency edges. |
| **executor** | The mechanism used to run an external command: on the host, or inside a docker/podman container. |
| **forge** | The hosting platform (gitcode; possibly others later) providing PRs, issues and tokens. |

## 3. Non-goals

- **Reimplementing upstream builds.** `cjdev` invokes each project's own build entry
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
  .cjdev/                         # everything cjdev owns; also the workspace marker
    config.toml                   # workspace config and manifest overrides
    bare/
      cangjie_compiler.git/       # single object store per project (bare)
      cangjie_runtime.git/        # remotes: upstream (read-only), origin (fork)
      ...
    build/<branch-set>/<profile>/ # out-of-tree build dirs, one per build unit
    dist/<branch-set>/<profile>/  # assembled SDK - the install target of every build.py
    cache/                        # created by the first build, not by `init`
      ccache/                     # shared across ALL branch sets - the point of the design
      misc/
    log/<branch-set>/             # per-run command logs
  fix-parser-ice-1234/            # a branch set, flat and directly in the root
    cangjie_compiler/             # git worktree - where the work actually happens
    cangjie_runtime/
    ...
  main/
    ...
```

Rationale: one object store per project (disk + fetch cost paid once), one worktree per
branch set (switching is instant and does not invalidate anyone's build dir), one build dir
per branch set × profile (no cross-branch clobbering), **one shared compiler cache**
(cross-branch reuse).

The tree is split by audience, not by kind. The root holds branch sets and nothing else,
because a branch set is the only path a person types or `cd`s into. Object stores, build
directories, caches, logs and the workspace config are the tool's business - they account
for almost all of the bytes and all of the churn - and live under `.cjdev/`, which is also
the workspace marker (CFG-7).

**Branch-set directories are flat, and the name is flattened one-way.** A branch set named
`fix/parser-ice-1234` gets the directory `fix-parser-ice-1234`, so no nesting ever appears
in the root. Only `/` is rewritten - on Linux it is the one character git allows in a
branch name and the filesystem does not. The mapping is *not* reversible (`fix/ice` and
`fix-ice` collide), with two consequences that are requirements, not details: the branch in
git remains the identity of a branch set and is read back with `git worktree list` rather
than from the directory name (CFG-9), and creating a branch set refuses a name whose
directory is already taken (BRANCH-1).

Hiding `dist/` is a deliberate trade: BUILD-10 prints the path to put on `PATH`, so it is
copied from output rather than found by browsing.

Directories appear when something first needs them, not all at `init`. An empty `cache/`
in a workspace that has never built anything is a promise the tool is not yet keeping.

### 4.2 Branch sets

A logical change rarely touches every project. Therefore:

- A branch set is identified by a **name** (e.g. `fix/parser-ice-1234`).
- For each project, the branch set resolves to either the branch of that name (if it
  exists) or a **base ref** - that project's default branch, pinned to the commit recorded
  in `refs/cjdev/base/<branch-set>` in that project's object store.
- Projects are enrolled into a branch set **lazily**: a project gets a real branch the
  first time it is modified, or on explicit `cjdev branch add <project>`.
- **Git is the only store of branch-set state.** The pin is a ref, the enrolment status is
  "does the branch exist", and the worktree list comes from `git worktree list`. There is
  no lock file: a second copy of state git already holds durably is a thing to keep in sync
  and to get wrong, and a single shared file would be a serialisation point in a fan-out
  that is otherwise per-project (PAR-2). Refs are per-project, atomic, and survive
  everything a workspace survives.
- The same reasoning covers fork URLs: they live in each object store's `origin` remote,
  because git needs them there to push at all. The workspace config never duplicates them.

### 4.3 Project set and build graph

Six repositories, all under `https://gitcode.com/Cangjie`, all with `main` as the default
branch. This is v1.0 manifest data, not an assumption baked into the code.

| Project | Holds | Role |
| --- | --- | --- |
| `cangjie_compiler` | `cjc` | The compiler. Also the default home of a change's tracking issue. |
| `cangjie_runtime` | `runtime/`, `stdlib/` | Two build units, one repository. |
| `cangjie_tools` | `cjpm/`, others | Package manager and the rest of the tooling. |
| `cangjie_test_framework` | a lit-like Python runner | Runs the suites. Builds nothing. |
| `cangjie_test` | test cases and configs | Data for the framework. Builds nothing. |
| `cangjie_multiplatform_interop` | interop layer | Build edges not yet established. |

A project is therefore **not** a build unit - `cangjie_runtime` and `cangjie_tools` each
hold several - and the dependency graph is over units:

| Unit | Lives in | Depends on |
| --- | --- | --- |
| `compiler` | `cangjie_compiler/` | - |
| `runtime` | `cangjie_runtime/runtime/` | - |
| `stdlib` | `cangjie_runtime/stdlib/` | `compiler`, `runtime` |
| `cjpm` | `cangjie_tools/cjpm/` | `compiler`, `runtime`, `stdlib` |

Every unit builds through a `build.py` in its own directory, exposing `build` and
`install` subcommands.

Nine further units are known by name but not by home or edges, which is question A. They
are absent from the manifest rather than guessed at (R11), and `cjdev build` therefore
does not accept them yet - the command takes its unit names *from* the manifest, so the
two cannot drift apart the way a hand-written command list did.

| Name | What it is |
| --- | --- |
| `stdx` | Standard library extensions |
| `cjfmt` | Formatter |
| `cjlint` | Linter |
| `cjcov` | Coverage tool |
| `cjtrace-recover` | Exception stack restoration tool |
| `hyprlang-extension` | HyperLangExtension |
| `cjls` | Language server (`LSPServer`, `LSPMacroServer`) |
| `cjprof` | Profiler |
| `cjcompat` | Compatibility tool |

### 4.4 Build environment baseline

No upstream image is published, so `cjdev` ships its own `Containerfile`. The baseline is
the environment `cangjie_build` documents, as captured in a Dockerfile already known to
work:

- Ubuntu 22.04, `x86_64`
- CMake 3.26.6 (upstream tarball, not the distro package), Ninja, GCC/G++, Make, Autoconf
- Clang/LLVM 15 (`libclang-15-dev`), on `PATH` via `/usr/lib/llvm-15/bin`
- GNUstep runtime 2.1 built for clang 14 (Objective-C interop)
- OpenJDK 17 (Java interop)
- Python 3 exposed as `python`
- OpenSSL, zlib, libcurl, libedit, libelf, libdwarf, ncurses5, rapidjson, gtest

Two things from that Dockerfile deliberately do **not** carry over: the SDK environment
variables (`ARCH`, `SDK_NAME`, `CANGJIE_VERSION`, `STDX_VERSION`) and the `envsetup.sh`
sourcing, both baked into `/etc/profile` against one fixed layout. `cjdev` owns that
wiring instead - the executor sets it per build unit and profile (ENV-5, ENV-11) - so the
image stays a toolchain and nothing more.

---

## 5. Functional requirements

Traceability to the original request: BRANCH←(1), BUILD←(2), CACHE←(3), ENV←(4),
TEST←(5), FORGE←(6), SYNC←(7). PAR ([§5.10](#510-par--parallel-execution)) has no
counterpart in the original request; it was added on 2026-09-04 because retrofitting
concurrency into commands that each drive their own subprocesses is a rewrite, not a
change.

### 5.1 BRANCH - synchronous multi-repository branching

| ID | Priority | Requirement |
| --- | --- | --- |
| BRANCH-1 | MUST | Create a branch set across all projects with one command; the branch name is identical in every participating fork. |
| BRANCH-2 | MUST | Switch to a branch set with one command; every project ends up on the corresponding branch or its pinned base ref. |
| BRANCH-3 | MUST | Branch sets are backed by `git worktree`, so switching never rewrites an existing checkout and never invalidates another branch set's build directory. |
| BRANCH-4 | MUST | List branch sets with, per project, the branch, the short SHA, the dirty flag and the ahead/behind counts vs `origin` and `upstream`. |
| BRANCH-5 | MUST | Delete a branch set: remove worktrees, optionally its build/dist directories, optionally the remote branches; refuse when a worktree is dirty unless forced. |
| BRANCH-6 | SHOULD | Enrol a project into an existing branch set lazily, branching from the pinned base ref rather than from whatever `upstream` looks like today. |
| BRANCH-7 | SHOULD | Operate on a subset via `--only`, `--exclude` and named project groups from the manifest. |
| BRANCH-8 | SHOULD | Refuse partially-applied state: preflight every project, and on failure report exactly which projects changed and how to resume. |
| BRANCH-9 | MAY | Import an existing manual checkout into a workspace instead of re-cloning. |

Sketch:

```
cjdev branch new fix/parser-ice --from upstream/default
cjdev branch switch fix/parser-ice
cjdev branch list
cjdev branch rm fix/parser-ice --remote --build
```

### 5.2 SYNC - keeping local, fork and upstream aligned

The reference procedure, per project:

```
git fetch upstream <default>
git branch -f <default> upstream/<default>       # no checkout: the worktree is untouched
git push --force-with-lease origin <default>     # optional, --fork
git rebase <default> <branch-set-branch>         # in the branch set's worktree
git push --force-with-lease origin <branch>      # optional, --push
```

| ID | Priority | Requirement |
| --- | --- | --- |
| SYNC-1 | MUST | One command fetches `upstream` and fast-forwards the local default branch for every project. |
| SYNC-2 | MUST | Updating the default branch MUST NOT check it out. Move the ref directly (`git branch -f`) so no worktree is touched and no rebuild is triggered. This replaces the `checkout` / `checkout -` dance. |
| SYNC-3 | MUST | Rebasing the current branch set onto the refreshed default branch is a distinct, explicitly-requested step. |
| SYNC-4 | MUST | Pushing to the fork is opt-in via a flag (`--fork` for default branches, `--push` for branch-set branches), never implicit. |
| SYNC-5 | MUST | All force pushes use `--force-with-lease`. Plain `-f` is never issued. |
| SYNC-6 | MUST | Before any history rewrite, save a backup ref (`refs/cjdev/backup/<branch>/<utc-timestamp>`) and print how to restore it. |
| SYNC-7 | MUST | Refuse to rebase a dirty worktree; `--autostash` opts into stashing. |
| SYNC-8 | MUST | The default branch name is detected per project (`refs/remotes/upstream/HEAD`), overridable in the manifest. Never hardcode `master`/`main`/`dev` - every project happens to be `main` today, and that stays manifest data. |
| SYNC-9 | MUST | On conflict, stop, report which projects are done / conflicted / untouched, and support `cjdev sync --continue` and `cjdev sync --abort`. |
| SYNC-10 | SHOULD | Enable `rerere` inside the workspace so the same conflict resolved in one branch set replays in the next. |
| SYNC-11 | SHOULD | `--dry-run` prints the exact git commands for every project without running any. |
| SYNC-12 | SHOULD | Detect and refuse the "upstream rewrote history" case rather than producing a silently wrong rebase. |

Sketch:

```
cjdev sync                          # fetch + ff default branches everywhere
cjdev sync --fork                   # ...and force-with-lease push them to the fork
cjdev sync --rebase                 # ...and rebase the active branch set on top
cjdev sync --rebase --push          # ...and publish the rebased branches
cjdev sync --only cangjie_compiler --dry-run
```

### 5.3 BUILD - building the SDK, whole or in parts

| ID | Priority | Requirement |
| --- | --- | --- |
| BUILD-1 | MUST | Build the whole SDK for the active branch set with one command, in dependency order derived from the manifest's **build-unit** graph ([§4.3](#43-project-set-and-build-graph)), not from the project list. |
| BUILD-2 | MUST | Build a single build unit, with `--only`, `--from <u>` (unit and dependents), `--upto <u>` (unit and dependencies). Naming a project selects all of its units. |
| BUILD-3 | MUST | Build recipes are declarative manifest entries that invoke each build unit's own `build.py` (`build`, then `install` into `dist/`). `cjdev` never reimplements or forks upstream build logic. |
| BUILD-4 | MUST | Extra arguments pass through verbatim to the underlying build script (`cjdev build compiler -- --foo`). |
| BUILD-5 | MUST | Build outputs live outside the source tree, keyed by branch set, profile and build unit; two branch sets never share a build directory. Where a `build.py` cannot build out-of-tree, the manifest marks that unit in-tree and `cjdev` reports the lost isolation rather than faking it. |
| BUILD-6 | MUST | Named profiles (`debug`, `release`, …) defined in the manifest and overridable per workspace. |
| BUILD-7 | SHOULD | Skip projects whose inputs are unchanged, using a stamp keyed on commit + dirty-tree hash + resolved build flags + toolchain identity; `--force` rebuilds anyway. |
| BUILD-8 | SHOULD | Fail fast by default, `--keep-going` to build everything buildable and report a summary. |
| BUILD-9 | SHOULD | Emit a per-project timing and cache-hit summary at the end of a build. |
| BUILD-10 | SHOULD | Assemble a usable SDK into `dist/<branch-set>/<profile>` and print how to put it on `PATH`. |
| BUILD-11 | MAY | Parallel builds of independent graph nodes, over the runner and job budget of [§5.10](#510-par--parallel-execution). |
| BUILD-12 | MAY | Cross-target builds. **Out of scope for v1.0**: the only target is the host, `x86_64` Linux, and a profile is a build type - never a target × build-type pair. |

### 5.4 CACHE - incrementality across branches

| ID | Priority | Requirement |
| --- | --- | --- |
| CACHE-1 | MUST | A single `ccache` store is shared by every branch set and every environment mode. |
| CACHE-2 | MUST | The cache is configured so that objects hit **across worktrees**, i.e. despite differing absolute source paths. In practice: `CCACHE_BASEDIR` at the workspace root plus `hash_dir = false`. Without this the shared cache is nearly useless - different worktree paths defeat it. |
| CACHE-3 | MUST | The cache is mounted into containers at the same path used on the host, so host and container builds share hits. |
| CACHE-4 | SHOULD | `cjdev cache stats` / `cjdev cache clear`, plus a size limit configured at workspace creation. |
| CACHE-5 | SHOULD | Document explicitly which parts of the build ccache does **not** accelerate (see [§9](#9-risks)), so the incrementality promise is not oversold. |
| CACHE-6 | MAY | Pluggable backend (`sccache`) behind the same interface. |
| CACHE-7 | MAY | `cjdev gc` to prune build/dist directories of stale branch sets by age or total size. |

### 5.5 ENV - host and containerised environments

| ID | Priority | Requirement |
| --- | --- | --- |
| ENV-1 | MUST | Every external command runs through a single **executor** abstraction. No command path bypasses it. |
| ENV-2 | MUST | Two executors: `host` and `container`. Container has first-class **docker** and **podman** backends; the difference is confined to the backend, never leaked into commands. |
| ENV-3 | MUST | Auto-detect the available runtime; overridable by config, `CJDEV_ENV`, and a per-invocation flag. |
| ENV-4 | MUST | Files produced inside a container are owned by the invoking user on the host (docker: `--user`; podman rootless: `--userns=keep-id`). Root-owned build artifacts are a defect. |
| ENV-5 | MUST | The workspace is mounted at a **fixed path** inside the container, identical across runs and images, so cache keys and debug paths stay stable. |
| ENV-6 | MUST | SELinux-labelled mounts (`:z`) where required, without breaking non-SELinux hosts. |
| ENV-7 | MUST | Ship a `Containerfile` buildable by both runtimes; `cjdev env build` builds it, `cjdev env pull` fetches a published one. No upstream image exists - the baseline `cjdev` must reproduce is [§4.4](#44-build-environment-baseline). |
| ENV-8 | MUST | The image reference (by digest) used for a build is recorded alongside the build stamp, so a toolchain change invalidates the stamp. |
| ENV-9 | SHOULD | `cjdev env shell` drops into the configured environment with the same mounts and env vars a build would use. |
| ENV-10 | SHOULD | `cjdev env doctor` verifies prerequisites for the selected mode (runtime present, image available, cgroups/userns sane, disk space, host toolchain versions). |
| ENV-11 | SHOULD | Same command, same result: switching between host and container mode must not require editing any config or path. |
| ENV-12 | MAY | Long-lived container reuse (`exec` into a running container) instead of one container per command, if start-up cost proves material. |

### 5.6 TEST - running the Cangjie test framework

| ID | Priority | Requirement |
| --- | --- | --- |
| TEST-1 | MUST | Run the `cangjie_test_framework` runner against the SDK in `dist/<branch-set>/<profile>`, with the environment wired up automatically. The framework is a lit-like Python tool that builds nothing; the cases it executes live in `cangjie_test`. |
| TEST-2 | MUST | Raw arguments pass through verbatim (`cjdev test -- --any-upstream-flag`). Shortcuts never block the underlying tool. |
| TEST-3 | MUST | Named **presets** (framework flags + suite selection + environment) resolved in layers: built-in → manifest → workspace config → user config → CLI flags. |
| TEST-4 | MUST | Select suites/subsets by short name or path, with tab-completable names. |
| TEST-5 | SHOULD | `cjdev test list` shows available presets and suites with their origin layer. |
| TEST-6 | SHOULD | Machine-readable results (`--json`) plus a stable non-zero exit code on failure, for CI use. |
| TEST-7 | SHOULD | `--rerun-failed` replays the previous run's failures. |
| TEST-8 | SHOULD | Build the SDK first if it is stale, unless `--no-build`. |
| TEST-9 | MAY | Compare a run against a stored baseline and report only new failures. |

### 5.7 FORGE - gitcode from the terminal

| ID | Priority | Requirement |
| --- | --- | --- |
| FORGE-1 | MUST | A `forge` port with a gitcode adapter. The adapter drives the official `gitcode` CLI (`auth`, `repo`, `issue`, `pr`, and the raw `api` escape hatch) rather than reimplementing the REST API - the same reasoning as NFR-3. No gitcode specifics leak into command or domain code. |
| FORGE-2 | MUST | Authentication is delegated to `gitcode auth login`. `cjdev` honours `GC_TOKEN` / `GITCODE_TOKEN` from the environment when set and otherwise relies on the CLI's own stored credentials; it never writes a token to a versioned file and never prints one, including in verbose logs and error output. |
| FORGE-3 | MUST | Open PRs for **exactly the projects that diverged** in the active branch set, in one command, using the branch-set name as the source branch. |
| FORGE-4 | MUST | Cross-link the PRs of one branch set through a single shared tracking issue - the existing convention upstream. The issue lives in the project the change centres on (`cangjie_compiler` by default); every PR body references it, and the issue lists every PR. |
| FORGE-5 | MUST | Preview the full PR title/body per project and require confirmation before anything is created; `--yes` for scripted use. |
| FORGE-6 | MUST | Idempotent: re-running updates the existing PRs rather than creating duplicates. |
| FORGE-7 | SHOULD | Create the tracking issue from the target repository's own template under `.gitcode/ISSUE_TEMPLATES`, read at run time rather than vendored, pre-filled from branch-set metadata and the commit range. |
| FORGE-8 | SHOULD | Optional AI-assisted drafting of the issue/PR body from the diff: opt-in flag, delegated to a user-configured external command, output always opened in `$EDITOR` before submission. Never auto-posted. |
| FORGE-9 | SHOULD | `cjdev pr status` shows CI state, review state and merge state for every PR in the branch set. |
| FORGE-10 | SHOULD | Order the PRs of a branch set by the build graph ([§4.3](#43-project-set-and-build-graph)) and state that order in the tracking issue, so reviewers merge dependencies first. |
| FORGE-11 | MAY | Fork creation and remote wiring for a project the user has not forked yet. |
| FORGE-12 | MAY | A second adapter (e.g. GitHub) to prove the port is real. |

**Confidentiality constraint on FORGE-8:** the diff of an unpublished change is sent to
whatever command the user configures. The tool must state this at the point of use and
default to off.

### 5.8 CFG - configuration and manifest

| ID | Priority | Requirement |
| --- | --- | --- |
| CFG-1 | MUST | Layered configuration: built-in defaults → user config → workspace config → `CJDEV_*` env → CLI flags, later wins. |
| CFG-2 | MUST | The project manifest (URLs, default branches, groups, dependency edges, build recipes, profiles) ships with `cjdev` and is overridable per workspace. |
| CFG-3 | MUST | The manifest carries a schema version and `cjdev` refuses a version it does not understand, with an actionable message. |
| CFG-4 | MUST | `cjdev status` reports workspace root, active branch set, per-project branch/SHA/dirty/ahead-behind, environment mode, cache stats and build freshness. |
| CFG-5 | SHOULD | `cjdev config show --origin` prints the effective config annotated with the layer each value came from. |
| CFG-6 | SHOULD | Everything `cjdev` owns lives under `.cjdev/` inside the workspace root and is removable with `rm -rf`; no hidden global state beyond the user config file. Deleting `.cjdev/` leaves the worktrees as ordinary directories, which is the intended way out of the tool. |
| CFG-7 | MUST | A directory is a workspace if and only if it holds `.cjdev/`; commands discover the root by walking up from the working directory. |
| CFG-8 | SHOULD | `cjdev manifest show` prints the effective manifest - project set, build-unit graph and the layer each entry came from. The shipped default is a file inside the wheel; without a way to read it back, "overridable per workspace" (CFG-2) is not discoverable by anyone who has not read the source. |
| CFG-9 | MUST | Branch sets are enumerated from git (`git worktree list` over the object stores), never by listing directories in the workspace root. Directory names are flattened and lossy ([§4.1](#41-workspace-layout)), and a stray directory a user creates in the root is not a branch set. |
| CFG-10 | MUST | `cjdev init` is also how a workspace is *changed*: re-run, it starts from the projects already on disk and adds or removes to match the new selection. Removing deletes that project's object store, so it confirms as a destructive action (UX-2). A workspace's project set is what its object stores say it is, never a list in a file that could disagree. |
| CFG-11 | MUST | `cjdev clean [path]` empties a workspace: worktrees, object stores and config all go, while the root directory itself is left standing so that nobody's shell ends up inside a directory that no longer exists. It confirms as destructive, and refuses while any worktree *outside* the root is still linked to a store inside it, because those would be left pointing at nothing. What it removes is read off the disk, never off the manifest, so a manifest that has since changed cannot make it miss a store. Distinct from CACHE-4's `cache clear` and CACHE-7's `gc`, which prune a workspace that goes on existing. |

### 5.9 UX - cross-cutting behaviour

Two consumers, one surface. Most of what follows applies to whoever is reading the output:
a person at a terminal, or an agent driving `cjdev` from a pipe with no terminal at all.
Where the two differ the agent is the stricter of the two - it cannot see a spinner, cannot
answer a prompt, cannot infer meaning from formatting, and pays for every line it reads -
so UX-6 and UX-11..18 state the machine contract explicitly instead of leaving it to
whatever the renderer happens to emit. Note the direction: decision 8 is `cjdev`
delegating *to* a model, this is an agent *calling* `cjdev`. Nothing here adds a model
SDK, a key or a network call, and the tool stays exactly as usable by hand.

| ID | Priority | Requirement |
| --- | --- | --- |
| UX-1 | MUST | `--dry-run` on every mutating command, printing the exact external commands that would run. |
| UX-2 | MUST | Destructive actions (history rewrite, force push, worktree/branch deletion, cache clear) confirm interactively; `--yes` for automation; never destructive by default. |
| UX-3 | MUST | Every external invocation is logged with its full argv, cwd and exit status; `-v` echoes it live. |
| UX-4 | MUST | On failure, report the failing project, the command, and the tail of its output - never a bare traceback. |
| UX-5 | MUST | Exit codes are meaningful and documented (0 ok, 1 operation failed, 2 usage error, 3 preconditions unmet). |
| UX-6 | MUST | `--json` on every command, not only the reporting ones. A reporting command emits what it observed; a mutating command emits what it changed, per project or build unit, in the same envelope. `--json` implies `--defaults` (UX-10) and never implies `--yes` (UX-2). |
| UX-7 | SHOULD | Shell completion for fish, bash and zsh, including dynamic completion of branch sets, projects, build units and presets. Completion runs without a workspace context, so it offers the shipped manifest's names until CFG-2's overrides are resolvable from the working directory alone. |
| UX-8 | SHOULD | Multi-project operations run with a stable, non-interleaved progress display and a final summary table. Under concurrency this is PAR-4. |
| UX-9 | SHOULD | Interrupting (`Ctrl-C`) leaves the workspace in a resumable state, never a half-rewritten one. |
| UX-10 | SHOULD | Commands that collect *settings* rather than *consent* run as an interactive wizard with defaults - `init` today, and every question ENV-3 and CACHE-4 add later. `--defaults` skips it and a non-TTY implies `--defaults`. This is a different flag from UX-2's `--yes` on purpose: one supplies answers, the other supplies permission to destroy something, and a single flag that did both would arm deletions in every CI script that only wanted to skip a wizard. |
| UX-11 | MUST | Machine output is a single versioned envelope: schema version, the command, an ok flag, the payload and the errors. Callers pin the version; fields are added, never repurposed, and a breaking change bumps it. A skill or a prompt that parses this output is written once, not re-derived after every release. |
| UX-12 | MUST | Under `--json`, stdout carries exactly one JSON document and nothing else; progress, logs, warnings and prompts go to stderr. Colour, spinners and every other ANSI escape are suppressed when stdout is not a TTY. A parser must never have to strip decoration to find the payload. |
| UX-13 | MUST | Every failure carries a stable machine-readable code, the project or unit it occurred in, and the command that resolves or resumes it - the same three in the text rendering (UX-4) and in the envelope. Codes are documented next to the exit codes (UX-5). A caller with no terminal recovers only from what the output states. |
| UX-14 | MUST | `cjdev` never blocks on stdin without a TTY. Where a terminal would prompt, a pipe fails with exit 3 and names the flag that supplies the answer (`--yes`, `--defaults`, or the option itself). For an unattended caller a hang is worse than a failure: a failure produces something to act on. |
| UX-15 | SHOULD | Captured subprocess output is bounded: a documented tail in the transcript and in the envelope, with the full text in the per-unit log file (PAR-11) whose path is part of the output. A build log runs to thousands of lines and belongs behind a path, not inlined into every caller's buffer. |
| UX-16 | SHOULD | `cjdev schema --json` describes the surface: commands, their flags, the exit codes, the error codes and the envelope version. It runs without a workspace, so a caller learns the surface from the tool rather than guessing at `--help` prose. |
| UX-17 | SHOULD | The package ships an agent-facing description of the workflow (`SKILL.md` / `AGENTS.md`): the command vocabulary, the read-only vs. mutating split, and the recovery paths. It is generated from the CLI, or checked against it in CI, so it cannot drift into being confidently wrong - which is worse than not shipping it at all. |
| UX-18 | MUST | Every question a wizard asks has a flag that *answers* it, not only one that skips it: `init` takes the project set on the command line. `--defaults` is not that flag - it takes what is already on disk, which is exactly what a caller setting a workspace up for the first time has none of, and a caller with no terminal cannot tick a checkbox instead. |

### 5.10 PAR - parallel execution

Most of what `cjdev` does is waiting: six `git fetch` against the same forge, six clones,
six read-only status queries, four builds of which two are independent. Doing that
sequentially wastes the majority of every command's wall time. Concurrency is therefore a
property of the **runner**, not a feature of individual commands - which is why the
structural requirements below are v1.0 blockers even though the parallel implementations
themselves are not.

| ID | Priority | Requirement |
| --- | --- | --- |
| PAR-1 | MUST | Every multi-project or multi-unit operation is expressed as a fan-out over independent units of work handed to one shared runner. A command never spawns threads or processes itself, so concurrency policy lives in exactly one place. |
| PAR-2 | MUST | The unit of concurrency is the **project** for git operations and the **build unit** for builds. Two units of work touching the same object store never run concurrently: parallel *across* projects, strictly serial *within* one. `git` does not serialise worktree, branch and fetch operations on a shared repository for us. |
| PAR-3 | MUST | `--jobs` / `-j N` on every fan-out command, defaulting to a bounded value derived from the workload (network-bound fan-out and CPU-bound fan-out do not share a default) and never unbounded. `-j1` forces strictly sequential execution in manifest order, and is the supported way to reproduce and debug a failure. |
| PAR-4 | MUST | Output is identical regardless of `-j`: per-unit output is captured and emitted whole, ordered by manifest or graph order rather than completion order. Progress display may be live and concurrent; the transcript, the summary table and the exit code may not depend on scheduling. This is the concurrent case of UX-8. |
| PAR-5 | MUST | Failure semantics do not change with `-j`. Fail-fast cancels work not yet started, lets in-flight work finish rather than killing it mid-write, and reports per unit which are done / failed / cancelled / untouched. Partial state is reported, never silent (BRANCH-8, SYNC-9, R9). |
| PAR-6 | MUST | Interactive confirmation (UX-2) and `--dry-run` (UX-1) are resolved **before** any fan-out. No worker ever prompts, and `--dry-run` prints in sequential order. |
| PAR-7 | MUST | `Ctrl-C` during a fan-out cancels pending work, waits for in-flight work to reach a consistent point, and prints the same per-unit summary as a failure would (UX-9). |
| PAR-8 | SHOULD | `init` clones and `sync` fetches run in parallel across projects. Network-bound and fully independent, this is the clearest win and the first one to land. |
| PAR-9 | SHOULD | The per-project read-only git queries behind `status` and `branch list` run in parallel, so `cjdev status` stays under a second as the project set grows (NFR-5). |
| PAR-10 | SHOULD | One job budget covers nested parallelism: `cjdev`'s own fan-out multiplied by the `-j` each `build.py` passes to make/ninja must not oversubscribe the machine. `cjdev` sets the inner value explicitly rather than letting each build script pick its own (blocked on [§10.2](#102-still-open) G). |
| PAR-11 | SHOULD | Per-unit log files under `log/<branch-set>/`, so concurrent runs do not interleave on disk either (UX-3). |
| PAR-12 | MAY | Forge operations (FORGE-3, FORGE-9) fan out too, at a low fixed concurrency and subject to the forge's rate limits - mutating and remote-throttled, so the payoff is smaller and the failure modes worse. |

Parallel builds of independent graph nodes are BUILD-11, and stay a MAY: they need the
build-unit graph, the job budget of PAR-10 and an answer to question B before the ordering
is even expressible.

---

## 6. Non-functional requirements

| ID | Priority | Requirement |
| --- | --- | --- |
| NFR-1 | MUST | Python ≥ 3.10, thin runtime dependency set. No dependency is added for a feature that shells out anyway. |
| NFR-2 | MUST | Domain and application layers are testable without git, network, containers or a forge account. Adapters are the only place that touches the outside world. |
| NFR-3 | MUST | Git is driven via the `git` CLI (worktrees, rerere, force-with-lease and credential helpers all behave as documented), not a reimplementation. |
| NFR-4 | MUST | Linux is the supported platform for v1.0. macOS is best-effort; nothing may be gratuitously Linux-only in the domain layer. |
| NFR-5 | SHOULD | `cjdev status` on a warm workspace completes in well under a second - it is going to be run constantly, possibly from a prompt. Six sequential `git` invocations do not fit that budget; PAR-9 is how it is met. |
| NFR-6 | SHOULD | Branch-set switching is O(worktree checkout) and does not touch build directories. |
| NFR-7 | SHOULD | The tool is usable offline for everything that does not inherently need the network. |

## 7. Architecture decisions

These are the decisions the requirements above imply. Recorded here until they graduate
into proper ADRs.

1. **Bare object store + worktrees, not N clones.** One fetch, one object store, instant
   branch-set switching, independent build dirs. This is the structural precondition for
   both BRANCH and CACHE.
2. **Executor port from day one.** Host vs. container is not a feature to bolt on later -
   retrofitting it means rewriting every command. Every subprocess goes through the port
   from the first commit.
3. **`cjdev` orchestrates, upstream builds.** Build recipes are declarative descriptions of
   how to call someone else's script. The moment `cjdev` contains compiler build knowledge
   it starts drifting from upstream.
4. **Git is the source of truth for "what is this branch set" - there is no lock file.**
   The base-ref pin is `refs/cjdev/base/<branch-set>`, divergence is "does the branch
   exist", and the worktrees come from `git worktree list`. Everything a lock file would
   record, git already records durably and per project; a second copy would add a file to
   keep in sync, a shared write point in an otherwise per-project fan-out (PAR-2), and a
   way for the two to disagree. The one thing a file would buy - exporting a branch set so
   somebody else can reproduce it - is not a requirement today. If it becomes one, the file
   comes back as an *export format*, never as the source of truth.
5. **Forge behind a port.** Partly for testability, partly because the gitcode surface is
   the least certain part of this design (see [§10.2](#102-still-open)) and must be
   replaceable without touching command code. The v1.0 adapter shells out to the official
   `gitcode` CLI; the port exists so a REST adapter can replace it if the CLI falls short.
6. **Layering (ports & adapters), with a deliberately thin core.** `cjdev` orchestrates
   external processes; it has no business rules to model. So the centre holds data and
   pure functions, not aggregates with lifecycles - functional core, imperative shell.
   - `domain/` - the manifest and build graph, the workspace path algebra, the observed
     per-project state. Immutable dataclasses and pure functions over them. No subprocess,
     no filesystem, no network (NFR-2).
   - `application/` - one use case per command, in three phases: gather (I/O) → decide
     (pure) → apply (I/O). Preflight (BRANCH-8) is the gather/decide half made explicit.
   - `infra/` - the only layer that touches the outside world: executors, the `git` CLI
     wrapper, config I/O, the forge adapter.
   - `cli/` - Typer wiring, argument parsing, rendering. Thin by construction.

   **Four ports**, because a port is only earned by a second implementation that will
   actually exist - and note that for three of the four, the second implementation is
   `--dry-run` or `--yes`, which users select on purpose rather than a seam invented for
   tests:
   - `Executor` - host vs. container (decision 2), and dry-run.
   - `FileSystem` - the workspace tree. UX-1 makes `--dry-run` a MUST on every mutating
     command, and a use case calling `Path.mkdir` directly escapes it; this was found by
     running `init --dry-run` and watching it create the workspace.
   - `Prompt` - a terminal, versus `--defaults`, `--yes` and a pipe (UX-2, UX-10).
   - `Forge` - gitcode today, another adapter to prove it (decision 5, FORGE-12).

   Git is *not* a port: NFR-3 already commits to driving the `git` CLI, and the CLI is
   behind `Executor`, so a second abstraction over the same subprocess is a tax with no
   payer. Neither is ccache, which is environment variables (CACHE-6 is a MAY, and
   `sccache` is configuration, not a different interface). Reads are not behind a port
   either: a probe is always real, or a dry run would decide from guesses.
7. **The runner owns concurrency.** Fan-out, the job limit, output ordering, cancellation
   and the per-unit summary live in one component that every multi-unit command hands work
   to ([§5.10](#510-par--parallel-execution)). The alternative - each command managing its
   own threads - makes `--dry-run`, `-j1`, deterministic output and resumable failure N
   separate implementations that drift. This is the same argument as decision 2: cheap now,
   a rewrite later.
8. **AI is a delegate, never a dependency.** Drafting an issue means handing a prompt to a
   command the user configured. `cjdev` gains no model SDK, no API key handling, and no
   behaviour that breaks when offline.

## 8. Milestones

| Milestone | Contents | Rationale |
| --- | --- | --- |
| **M1 - workspace & git** | CFG-1..4, BRANCH-1..5, SYNC-1..9, UX-1..6, UX-11..14, UX-18, PAR-1..9 | The daily pain is branch juggling, and this milestone alone is already worth using. PAR-1..7 are structural and belong here for the same reason the executor port does; PAR-8/9 are the payoff on clone, fetch and status. The machine contract is here for that same reason: an envelope, stream discipline and error codes retrofitted across five milestones of commands is a rewrite of every renderer. |
| **M2 - build & cache** | BUILD-1..6, CACHE-1..3, PAR-10..11, executor (host only) | Delivers the incrementality promise. The job budget only becomes meaningful once something nests builds inside the fan-out. |
| **M3 - containers** | ENV-1..10 | Slots into M2's executor port with no command changes - that is the test of decision 2. |
| **M4 - test** | TEST-1..6 | Depends on a working build. |
| **M5 - forge** | FORGE-1..7, FORGE-9 | Needs branch sets, and the branch state in git, to know what to publish. |
| **M6 - polish** | FORGE-8, BUILD-7..10, BUILD-11, PAR-12, UX-7..9, UX-15..17, completions | Everything that is a multiplier rather than a capability. |

## 9. Risks

| # | Risk | Mitigation |
| --- | --- | --- |
| R1 | **ccache only covers C/C++.** Cangjie-language parts of the SDK are compiled by `cjc` and get nothing from ccache; their incrementality depends entirely on the upstream build system. The cross-branch reuse promise (CACHE) is therefore partial. | Measure before promising. Document the split (CACHE-5). Investigate whether the Cangjie-side build has a usable cache of its own. |
| R2 | **CMake reconfiguration per worktree** can eat the savings ccache produces. | Measure. Consider a per-branch-set persistent configure step, or a shared configure cache. |
| R3 | **Absolute paths defeat the shared cache.** Different worktree path ⇒ different hash ⇒ zero hits. | CACHE-2 (`CCACHE_BASEDIR` + `hash_dir = false`) and ENV-5 (fixed container path) are not optional details; they are the feature. |
| R4 | **Disk growth.** Branch sets × profiles × build dirs is measured in tens of GB. | CACHE-7 (`gc`), size reporting in `status`, opt-in build-dir removal on branch-set deletion. |
| R5 | **Force-push data loss.** SYNC rewrites published history by design. | `--force-with-lease` only (SYNC-5), backup refs (SYNC-6), confirmation (UX-2), `--dry-run` (SYNC-11). |
| R6 | **gitcode CLI coverage.** The official CLI is the chosen client, but which of its `pr` / `issue` verbs this workflow needs - and whether cross-repo linking is expressible without dropping to `api` - is unverified. | Spike before M5; forge port (decision 5) contains the blast radius. |
| R7 | **Upstream build scripts change.** Flags and entry points move. | Recipes are data, not code (BUILD-3); pass-through args (BUILD-4); pin the manifest schema (CFG-3). |
| R8 | **Submodules / LFS in a worktree** behave differently from a plain clone. | Verify per project during M1; if present, handle explicitly rather than by accident. |
| R9 | **Partial cross-repo operations.** A failure mid-way leaves projects inconsistent. | Preflight everything (BRANCH-8), resumable `--continue`/`--abort` (SYNC-9), never a silent partial success. |
| R10 | **Scope.** Seven feature areas is a lot for one tool. | Milestones are ordered so each is independently useful; M1 ships before M2 starts. |
| R11 | **The build graph is only partly known.** The units and edges of `cangjie_tools` beyond `cjpm`, and of `cangjie_multiplatform_interop`, are not established. | The graph is manifest data, not code (CFG-2). Ship with the four confirmed units; add edges as they are verified. |
| R12 | **Concurrency turns latent bugs into intermittent ones.** Interleaved output, scheduling-dependent exit codes, two operations racing on one object store, and failures that reproduce only at `-j8` are the standard tax, and they are far worse to debug than the sequential runs they replace. | The requirements that make this tractable are structural, not optional: one runner (PAR-1), per-project serialisation (PAR-2), scheduling-independent output and exit codes (PAR-4/5), and `-j1` as a first-class supported mode for reproducing anything suspicious (PAR-3). |
| R14 | **The machine surface is a compatibility contract.** An envelope, error codes and a shipped agent doc are things callers pin. Once someone's prompt or script depends on a field, renaming it breaks a caller that cannot report the break - it just starts doing the wrong thing quietly. | Version the envelope from the first release and change it additively (UX-11), document the error codes next to the exit codes (UX-13), and generate the agent doc from the CLI instead of maintaining a second copy by hand (UX-17). |
| R13 | **The parallel win may be smaller than it looks.** If the forge throttles concurrent fetches, or if builds are already saturating the machine through their own `-j`, fan-out buys little and costs complexity. | Measure `init` and `sync` at `-j1` against `-j6` before extending fan-out anywhere else. PAR-10 exists precisely so the CPU-bound case does not oversubscribe. |

## 10. Open questions

Answered on 2026-09-03 where listed as resolved. The rest still block the requirements
they name.

### 10.1 Resolved

| # | Question | Answer |
| --- | --- | --- |
| 1 | Project set | Six repositories under `https://gitcode.com/Cangjie`, default branch `main` everywhere - enough for the first iteration. Listed in [§4.3](#43-project-set-and-build-graph). |
| 2 | Dependency graph | Partly known, and the important finding is that graph nodes are **build units**, not projects: `cangjie_runtime` and `cangjie_tools` each hold several. Units are named flat (`stdlib`, not `cangjie_runtime/stdlib`) because that name is what a user types. Confirmed edges in [§4.3](#43-project-set-and-build-graph); the rest in [§10.2](#102-still-open). |
| 3 | Build entry points | A `build.py` in each build unit's directory, with `build` and `install` subcommands. Out-of-tree support is per unit and unverified ([§10.2](#102-still-open)). |
| 4 | `cangjie_test_framework` | Its own repository in the same organisation: a lit-like Python runner that builds nothing. The cases and configs it runs live in `cangjie_test`. |
| 5 | gitcode API | An official CLI exists - `gitcode` / `gc`, <https://gitcode.com/gitcode-cli/cli> - offering `auth`, `repo`, `issue`, `pr`, `actions` and a raw `api` escape hatch, with tokens read from `GC_TOKEN` / `GITCODE_TOKEN`. The forge adapter wraps it instead of the REST API (FORGE-1/2). |
| 6 | Targets | Host only, `x86_64` Linux, for v1.0. A profile is a build type, not a target × build-type pair; BUILD-12 is out of scope. |
| 7 | Base image | None published. `cjdev` ships its own `Containerfile`; the baseline it must reproduce is [§4.4](#44-build-environment-baseline). |
| 8 | Issue template | Lives under `.gitcode/ISSUE_TEMPLATES` in the target repository. `cjdev` reads it at run time rather than vendoring a copy that will drift (FORGE-7). |
| 9 | Multi-repo PR conventions | A convention exists: one shared tracking issue, usually in `cangjie_compiler`, that the change's PRs link to. `cjdev` follows it rather than inventing its own (FORGE-4). |

### 10.2 Still open

| # | Question | Blocks |
| --- | --- | --- |
| A | The build units and edges of `cangjie_tools` beyond `cjpm`, and of `cangjie_multiplatform_interop`. | BUILD-1/2 for those projects (R11) |
| B | Whether each `build.py` supports an out-of-tree build directory, and where its `install` places output. | BUILD-5, the `build/` and `dist/` layout |
| C | How the `cangjie_test_framework` runner locates an SDK, and what its suite / preset vocabulary is. | TEST-1/3/4 |
| D | The fields of the `.gitcode/ISSUE_TEMPLATES` entries, and which of them are derivable mechanically rather than by an LLM. | FORGE-7/8 |
| E | Which `gitcode` CLI subcommands cover the PR and issue flow, and whether cross-repo linking needs the `api` escape hatch. | FORGE-3/6/9 (R6) |
| F | What `envsetup.sh` is actually responsible for, so the executor can reproduce it instead of sourcing a file baked into an image. | ENV-5/11 |
| G | Whether each `build.py` accepts a job count and passes it down to make/ninja, or picks its own. Without that, the nested job budget cannot be enforced - only guessed. | PAR-10, BUILD-11 (R13) |
| H | Whether gitcode rate-limits concurrent fetches from one account, and at what threshold. | PAR-8 defaults, PAR-12 (R13) |
