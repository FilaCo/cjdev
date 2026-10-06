# ADR-0013: The workspace config is a real override layer over the bundled manifest

Status: accepted, 2026-09-18. Closes #13.

## Context

`init` wrote `.cjdev/config.toml` into every workspace it created, and nothing read it
back — the manifest came from the copy bundled in the wheel, every time. Meanwhile the
shipped files already promised the opposite: the bundled manifest's header said a
workspace "overrides any part of it in its own `.cjdev/config.toml`", and the template
`init` writes advertised a show command.

A design tension to settle: the workspace template is comment-only, but the bundled
parser required `schema_version` — the workspace layer needed defaults for what the
bundled layer already supplies, not a copy of its gate.

## Decision

A command inside a workspace layers that workspace's `.cjdev/config.toml` over the
bundled manifest; the bundled manifest alone applies outside. Overrides are partial —
missing keys inherit from the layer below — and a workspace may **add** projects and
build units the bundle does not know, but not remove bundled ones (v1 scope: removal
interacts with held-projects reporting and nothing needs it yet). A comment-only file,
exactly what `init` writes, is valid and changes nothing.

Every refusal names the file it came from; reference validation (build unit → project,
`depends_on`, group membership, `default_group`) runs on the **effective** result, so
two individually valid layers cannot combine into a dangling reference without the
error saying which layer introduced it. `schema_version` keeps its gate, naming the
workspace file.

The layering itself is a pure function over `domain/` dataclasses (two manifests in,
one out), assertable with nothing on disk; `tomlkit` types stay inside
`infra/config.py`.

`cjdev config show` prints the effective manifest; under `-v` every value is annotated
with the layer it came from — possible only after ADR-0012 fixed `-v` to be
presentation-only.

## Consequences

The command name is `config show`, not the `manifest show` the bundled header once
promised: the command shows the effective *config*, of which the bundled manifest is
one layer, and `config show` was the name `init` already printed to users (the
bundled header and the template were reconciled to it). Configuration is now a real
promise the tool keeps rather than a placeholder file.
