# cjdev docs

| Where | What | Rule |
|---|---|---|
| [architecture.md](architecture.md) | living rules | the layers, the ports, the shape the code holds to; changed in the same PR as the code they describe |
| [conventions.md](conventions.md) | vocabulary | the words, and what a comment and a test are for |
| [adr/](adr/) | decisions taken | one decision per file, ≤ 1 page; numbered by issue, never rewritten, superseded by a new one |
| [adr/README.md](adr/README.md) | the ADR index | **generated** by `tools/adr_index.py`; a test fails when it is stale - never edit it by hand |

How to build, test and commit: [CONTRIBUTING.md](../CONTRIBUTING.md). The same, for
coding agents: [AGENTS.md](../AGENTS.md).

## When a change writes here

Only when it tells the next reader something the docs and the code do not already say.
A change that follows the rules written here writes nothing.

| Writes | When |
|---|---|
| a rule (architecture.md) | the change sets a constraint future code must keep, and the compiler does not check it |
| an ADR | there was a real choice: alternatives weighed, one taken, a reason that is not obvious from the code |
| nothing | the story of the PR, its measurements included: the PR description; a rule or ADR cites the conclusion |
| nothing | the list of what exists (commands, fields, tables): that is the code and `cjdev -h` |

One fact, one place: a rule is stated once, in architecture.md; an ADR says why,
CONTRIBUTING.md and AGENTS.md link to both rather than repeat them.

## Adding an ADR

The number is the issue's (the issue-first workflow opens it before any PR), the file
name is `NNNN-slug.md` under `adr/`, and the index is regenerated:

```bash
python tools/adr_index.py
```

A test (`tests/test_adr_index.py`) fails CI when the index is stale. The template and
the exact Status-line contract are in the generated index header.
