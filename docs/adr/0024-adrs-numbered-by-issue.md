# ADR-0024: ADRs are numbered by their issue, and the index is generated

Status: accepted, 2026-10-06. Closes #24.

## Context

cjls (ide4cj/cjls) records decisions in `docs/adr/` — one per file, never rewritten,
superseded by a new one — and the process there has two properties that break under
parallel PRs:

- **The sequential number is allocated when the ADR is written.** Two PRs opened
  together take the same next number, and one renumbers: its title, its file name,
  and every citation already written into it.
- **The index is hand-edited.** Every ADR adds a row to the table in
  `docs/adr/README.md` and may edit another (a supersede), so the same two PRs
  conflict on the same lines. Squash-merge does not resolve this; a human does,
  every time.

This repo already had the piece cjls lacks: every change starts with an issue
(ADR-0009), so a number is allocated — uniquely — when the issue is created, before
any PR exists.

## Decision

**An ADR's number is the number of the issue whose resolution is that decision.**
Uniqueness is free: the number is allocated when the issue is created, and two
parallel PRs hold two different issues. Numbering is sparse — an issue that resolves
without a real choice leaves no ADR, and gaps in the sequence are expected, so the
sequence carries no meaning beyond identity.

**The index is generated, never hand-edited.** `tools/adr_index.py` reads the ADR
files' `# ADR-NNNN:` headings and `Status:` lines and writes `docs/adr/README.md`:
the rules, the template, the table. `tests/test_adr_index.py` regenerates it and
fails on a difference, so a stale index fails the pytest job CI already runs — the
same shape as `ruff format --check`.

**One ADR per real decision: the decision and why, not how it was reached.** A
benchmark's table goes in the PR, the ADR keeps the result. An accepted ADR is not
rewritten; a new one replaces it, saying "supersedes ADR-NNNN". In discussion
`D7` ≡ `ADR-0007`.

## Consequences

Adding an ADR is `git switch -c …`, write the file, run `python tools/adr_index.py`,
commit both — nothing to coordinate with other PRs, nothing to renumber. A reviewer
sees the index diff and the file together. The cost is the sparse sequence: `0001`
does not exist, and that is fine — cjls's dense sequence is a byproduct of its
numbering, not a value of its own. The extraction of the decisions already embedded
in `docs/architecture.md` into these files was this issue's one-time act;
architecture.md remains the living rules, the ADRs the record.
