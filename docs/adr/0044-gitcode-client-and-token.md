# ADR-0044: GitCode is a `Forge` port over urllib, and the token is GITCODE_TOKEN, then git's credential

Status: accepted, 2026-10-09. Closes #44.

## Context

`cjdev issue new` is the first command that talks to GitCode, and `cjdev pr` (#47) and
`cjdev start` (#45) will reuse whatever it builds. The API was verified by hand: v5,
Gitee-style - `POST /repos/{owner}/issues` with `repo` in the JSON body, labels as one
comma-separated string, `Authorization: Bearer`. The token the user already keeps in
git-credential-manager for gitcode.com is accepted. The issue forms are YAML, and the API
does not enforce them.

## Decision

**`Forge` is a port** in `application/ports.py`, implemented by `infra/gitcode.py`:
`GitCodeForge`, and `DryRunForge`, which prints the request and files nothing. The second
implementation is `--dry-run`, so it earns the port by the usual test. Its transport is
`urllib`: one JSON request per call needs no HTTP library.

**The token is `GITCODE_TOKEN`, else `git credential fill` for `https://gitcode.com`**,
looked up only when a request is about to be sent, and never read from the workspace
config. The variable comes first because it is the one a caller sets on purpose; a stored
credential that always won could never be overridden for one run. The credential helper
is how cjdev reaches the system keyring: git-credential-manager, libsecret and
osxkeychain all answer through it, so a user with a working `git push` needs no setup.
Every prompt is off (`GIT_TERMINAL_PROMPT=0`, an empty `GIT_ASKPASS`,
`GCM_INTERACTIVE=never`), so a host with no credential is a refusal naming the variable,
not a dialog. It runs outside `Executor`, because the workspace log and `-v` record what
a command printed, and this output is a secret.

**Forms are read with PyYAML**, inside `infra/issue_template.py`, the way TOML stays in
`infra/config.py`. The standard library has no YAML, and the forms use flow lists and
block scalars.

Rejected: `requests`/`httpx` (a dependency for one POST); the `keyring` package
(SecretStorage and `cryptography` on Linux, and a second store for a token git already
holds); the credential before the variable, as first proposed on the issue (the
variable could then never win); a duplicate check before filing (the list endpoint
ignores `q`, so it means paging through every issue of the repository).

## Consequences

A token that only lives in a keyring git does not use has to be exported as
`GITCODE_TOKEN`. Hosts other than gitcode.com are refused before anything is sent.
`cjdev pr` and `cjdev start` add methods to `Forge` rather than a client of their own.
