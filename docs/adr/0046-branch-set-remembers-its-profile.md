# ADR-0046: A branch set remembers its profile, and `cjdev test` runs against its dist

Status: accepted, 2026-10-09. Closes #46.

## Context

On branch set `fix_objcimpl_inheritance_diag` the SDK was built in debug, `cjdev build
compiler` defaulted to release, and the release dist got a fresh `cjc` and no std `.cjo`.
`cjdev env run` pointed `CANGJIE_HOME` at release too. Tests were run by hand with a
`main.py` line that needs the right test list, config, dist and three variables.

## Decision

**A branch set has a record, `.cjdev/state/<set>.toml`, and its `[build] profile` is the
profile of the last successful full build.** One file per branch set, so two sets never
write one file and removing a set removes its record. It is the place #45 adds the task
to: each writer updates its own table through `tomlkit` and keeps the rest, so a write of
the profile does not drop a `[task]` beside it. `build`, `env run`/`shell` and `test`
default to it, release when there is none; `-p` still wins.

**A partial build in a profile other than the recorded one is refused when units outside
the selection have no build directory in that profile**, naming them. Every unit outside
the selection, not only graph dependencies: nothing in the graph says the compiler needs
stdlib, but a dist without it compiles nothing. "Built" is the unit's build directory
existing for that environment and profile, which needs no new state and holds for builds
made before the record existed.

**`cjdev test <path>...` is one `main.py` run per suite**, inside the build environment
with the branch set's dist and `CANGJIE_TEST`. The suite is where the path sits under
`cangjie_test/testsuites/` (LLT or HLT); the test list and config come from a table keyed
by suite and target, read off upstream's file names, since upstream publishes no pairing.
cjdev passes `-pFAIL --fail-verbose`, `-j <cores>` and `--temp_dir`, `--log_dir`,
`--json_output` under `.cjdev/build/<set>/test/<env>/<profile>/<suite>/`; arguments after
`--` come last, and argparse keeps the last of a repeated option, so they override any of
it, the table included.

**The summary is read from `--json_output`, not the console.** The console is a progress
display and its summary line is a format nobody promised to keep. A failed case whose
output says `<tool>: command not found` is counted per tool rather than listed.

Rejected: one record for the whole workspace (concurrent writes from two sets); a list of
built units in the record (blind to every existing build, and a second truth beside the
build directories); the suite table in the manifest (a schema change for data no
workspace has needed to override yet, and `--` already overrides it).

## Consequences

The framework writes `cost_time.csv` beside the config it is given, inside the
`cangjie_test` worktree, and no flag moves it. A host the table does not know is a
refusal whose remedy is passing `--test_list` and `--test_cfg` after `--`.
