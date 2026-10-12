# ADR-0045: A task is a branch set and its issue, kept in the branch set's record

Status: accepted, 2026-10-12. Closes #45.

## Context

`cjdev branch new` took a bare name: the issue lived in the user's head, and the set was
cut from whatever `upstream` was at `init`. `pr` (#47), `ship` (#48) and `done` (#49)
all need the issue, the project it lives in and, later, the PRs, without being told
again.

## Decision

**The task is a `[task]` table in `.cjdev/state/<set>.toml`**, the record ADR-0046 made
for the profile: `issue` (the URL) and `home` (the project the issue lives in). One file
per set, one table per concern, each writer setting only its own keys through `tomlkit`
and keeping the rest. No `[task]` means the set was made by `branch new` and has no
task yet; `issue` absent means a task started without one. The PRs of #47 go under the
same table, as `[task.prs]` keyed by project, so attaching an issue keeps them.

**The URL is the identity**, not a number: it names the repository, and a number alone
is ambiguous across seven projects. The home is derived from it, as the project whose
`upstream` is that repository, so it cannot disagree with the issue.

**`cjdev start <issue-url>`** reads the issue through `Forge.read_issue`, names the set
`issue-<n>-<slug of the title>` (`--name` overrides; a title with no ASCII leaves
`issue-<n>`), fetches `upstream` in every held project and then runs `branch new`, whose
base is `upstream`'s recorded default branch, now fresh. The record is written only
once every checkout succeeded. A dry run reads the issue for real, like every probe.

**Without an issue**, `branch new` stays as it was, and `start --no-issue NAME` is the
same plus the fetch and a `[task]` with only `home`: `--home`, else `[forge] issue_home`
(default `cangjie_compiler`, the one place the name appears). `[forge]` because
ADR-0043 kept that section for GitCode settings. `issue attach <url>` writes the issue
and its home later, replacing and naming any previous one; it sends nothing to GitCode.

**`cjdev sync`** fetches `upstream` and fast-forwards a branch with no commits of its
own; a diverged one is reported with `git rebase upstream/<default>`, never rebased.

Rejected: one workspace-wide task file (two sets writing one file); the issue number
as the key (ambiguous across projects); rebasing in `sync` (rewrites what may be
pushed); validating `attach` against the API (a token for a write that is local).

## Consequences

A typo in an attached URL is found by the first command that reads the issue. A task's
`home` is frozen when it is written, so changing `issue_home` later moves only new tasks.
