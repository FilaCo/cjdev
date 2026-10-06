# ADR-0018: The positional argument is the subject; options carry context

Status: accepted, 2026-09-18. Closes #18.

## Context

`docs/conventions.md` fixed the vocabulary — the thing `branch new` creates is a
**branch set**, the tree it is created in is a **workspace** — and the CLI was the one
place neither word reached the user: the first argument was spelled `name` and the
workspace was a second positional argument. How the CLI spells its arguments is a
decision every future command inherits, and it was being made ad hoc per command.

## Decision

The positional argument is the command's subject; options carry context. For
`branch new` the subject is the branch set (`branch_set`, named by its vocabulary
term, the usage line reading `{branch_set}`) and the workspace is context:
`-w/--workspace PATH`, defaulting to the cwd with the same walk-up semantics git
uses to resolve a repository. Where the workspace *is* the subject — `status`,
`config show` — it keeps its positional path.

The argument/option split became a convention in `docs/conventions.md`, so the next
command inherits the rule rather than re-deciding it.

## Consequences

`--json` payloads and the journal are unaffected: the journal records the same argv
(`["branch", "new", BRANCH_SET]`), the workspace stays out of it. New commands get
their shape for free, and the help text carries the vocabulary the docs fixed.
