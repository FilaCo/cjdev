---
name: cjdev
description: Work in a cjdev workspace of the Cangjie SDK - branch sets across projects, out-of-tree builds, LLT/HLT test runs, commits and pushes across projects, upstream issues. Use whenever the cwd is under a directory holding `.cjdev/`, or the task is to build, test, commit, push or file an issue for cangjie_compiler, cangjie_runtime, cangjie_stdx, cangjie_tools or cangjie_test.
---

# cjdev

`cjdev -h` and `cjdev <command> -h` are the reference and always match the installed
version. This page is what the help does not say.

## Words

- **project**: one git repository (`cangjie_compiler`, `cangjie_runtime`, ...).
- **build unit**: one buildable part of a project (`compiler`, `runtime`, `stdlib`, ...).
  A project may hold several, and `build` takes either.
- **workspace**: the directory holding `.cjdev/`. Commands find it by walking up from the cwd.
- **branch set**: one branch name checked out in every project, under
  `<workspace>/<branch name with / as ->/<project>/`.
- **upstream** is the canonical repository and is never pushed to. **origin** is the
  user's fork, the only remote `push` writes to.

## The cwd is the context

`build`, `test`, `commit`, `push`, `env run` and `issue new` act on the branch set the
cwd is inside, and have no flag to name another. `cd` into the branch set first.
Outside one they refuse with exit code 3.

## The usual flow

```bash
cjdev branch new fix/parser-ice      # once; then cd fix-parser-ice/cangjie_compiler
cjdev build                          # every unit, in dependency order
cjdev build compiler                 # one unit and what it needs
cjdev test compiler/CJMP/objc        # a path under cangjie_test/testsuites/LLT or HLT
cjdev commit -a -m "fix(sema): ..."  # one message in every project with changes
cjdev push                           # to origin, prints where to open each PR
```

- A build log is teed to `.cjdev/log/<branch set>/<unit>.log`. Read it rather than
  rebuilding with `-v` to see an error.
- Do not run `build.py`, `cmake` or the upstream scripts by hand. `cjdev env run -- CMD`
  runs one command with the exact environment, mounts and variables a build uses.
- `build` and `test` default to the profile of the branch set's last full build.
  Pass `-p` only when the task asks for another one.

## Reading results

- Pass `--json` where it exists: `status`, `branch new`, `build`, `config show`.
  Stdout then holds one JSON document and nothing else, everything else goes to stderr.
  The envelope is `{schema, command, ok, data, errors}`. Stop if `schema` is not `1`.
- Each error carries a `code`, a `subject` (the project or unit) and sometimes a
  `remedy`, the command that fixes it. Follow a remedy; do not invent one.
- Exit codes: `1` the operation failed, `2` the invocation is wrong, `3` the workspace
  is not ready for it (no workspace, not in a branch set, no terminal to ask at).
- `cjdev status` shows each project's branch, dirty state and `origin ↑N` for unpushed
  commits. Run it before `commit` or `push` when unsure of the state.

## Ask the user first

- **`cjdev init`** asks which projects to fetch and needs a terminal. Do not run it;
  ask the user to.
- **`cjdev push`** publishes to the user's fork. `--force-with-lease` rewrites it.
- **`cjdev issue new PROJECT -t FORM`** files a public issue upstream. It opens `$EDITOR`,
  which an agent cannot use: write the draft, show it, then send it with
  `--body-file PATH`. `--dry-run` prints the request without sending it.

Every mutating command takes `--dry-run`, which prints the commands and runs none.
