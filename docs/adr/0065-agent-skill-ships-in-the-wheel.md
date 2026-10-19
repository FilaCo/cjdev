# ADR-0065: The agent skill ships in the wheel and installs user-level

Status: accepted, 2026-10-12. Closes #65.

## Context

Coding agents drive cjdev from `cjdev -h`. The help says what each command takes, not what
an agent gets wrong: that the cwd is the branch set, that a project is not a build unit,
how to read `--json`, and which commands need a human. Typer generates no skill; `typer
utils docs` emits a Markdown copy of the help.

## Decision

**The skill is hand-written, `infra/data/SKILL.md` in the Agent Skills format, and carries
only what the help does not.** It travels in the wheel, so it describes the installed
version. A test checks it against the CLI: every command it names exists, its list of
`--json` commands is the real one, and the schema it pins is `SCHEMA`.

**`cjdev skill install` writes it to `~/.claude/skills/cjdev/` by default, not into the
workspace.** Claude Code looks for project skills from the cwd up to the git repository
root, and every project of a branch set is a repository of its own. Probed with Claude Code
2.1.296: a skill in `<workspace>/.claude/skills` is found from the workspace and from a
branch set directory, and not from inside a project, where agents work. `--dir` names
another skills directory, such as `~/.agents/skills` for Codex. `cjdev skill show` prints
it for anything else.

Rejected: a generated reference (a stale copy of `-h`, which an agent reads live); install
into the workspace (invisible from inside a project); `init` installing it unasked (a write
outside the workspace that nobody agreed to).

## Consequences

A user-level copy outlives the cjdev that wrote it: an upgrade that changes the skill needs
`cjdev skill install` again, which reports `updated`.
