# ADR-0027: Third-party sources are fetched by cjdev and linked by commit

Status: accepted, 2026-10-09. Closes #27.

## Context

The compiler's configure fetches its gitignored sources itself. boundscheck is an
unchecked `execute_process` clone whenever `third_party/boundscheck` is missing;
llvm-project and flatbuffers are ExternalProject downloads into the build directory
unless `third_party/llvm-project` or `third_party/flatbuffers/CMakeLists.txt` exists.
A clone interrupted mid-checkout leaves a directory every later configure trusts:
`configure_file` drops a `CMakeLists.txt` into it, and configure dies with "No SOURCES
given to target" on every retry. The fix by hand is `rm -rf`, and nothing says so.

## Decision

**Third-party sources are per-unit manifest data**: `path`, `upstream`, `ref`, with
upstream's refs. Before a unit builds, under its lock, cjdev resolves the ref with
`git ls-remote` (a 40-hex ref is a commit already), fetches that commit shallowly into
`.cjdev/cache/third_party/<name>/<commit>.partial` and renames it to `<commit>`. **The
rename is the completion marker**: a commit directory exists only once its fetch
finished, and a leftover `.partial` is deleted and fetched again. A moved tip is a new
commit, fetched beside the old one.

**The path upstream checks becomes a relative link to that commit.** It is the one
input all three checks honour: `build.py` passes no `-D` through and boundscheck's path
is fixed. ADR-0039's case against links does not apply here: nothing upstream wipes
these paths or walks up out of them, and upstream already ignores all three. A
directory there that cjdev did not link is a refusal naming `rm -rf`: a complete
upstream clone and a partial one look the same.

Fetching runs on this machine, never in the container, with git's credentials. A
failed fetch is an error naming `cjdev build <unit>`; an unreachable upstream keeps a
commit already linked, and is an error only when nothing has been fetched.

Rejected: a marker file inside the tree (the rename is atomic and needs none), a clone
per branch set (llvm is gigabytes), moving the tree in like scratch (one tree, several
branch sets at once), `clone --branch` (the tip can move between resolve and clone).

## Consequences

One fetch serves every branch set and profile, and upstream's configure writes into
that shared tree: boundscheck's `CMakeLists.txt`, the libraries llvm's patch step
copies into `utils/`. Old commits stay under `.cjdev/cache/third_party/` until something
removes them. A workspace with its own llvm writes `third_party` for the compiler in
`.cjdev/config.toml`, or `[]`. libxml2, cloned only for cjdb, is still upstream's.
