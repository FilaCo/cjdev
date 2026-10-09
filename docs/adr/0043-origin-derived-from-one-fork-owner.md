# ADR-0043: origin is derived from upstream and one fork owner

Status: accepted, 2026-10-09. Closes #43.

## Context

`cjdev push` needs a remote to push to, and a workspace made by `init` had `upstream`
only. Every project's fork lives at the same place relative to its upstream - the same
host, the same repository name, the user's namespace instead of `Cangjie` - so typing
six URLs would be six copies of one fact. Guessing the owner from a git or OS user name
is wrong for anyone whose forge account is named differently.

## Decision

**One workspace setting, `[forge] fork_owner`, in `.cjdev/config.toml`.** A setting like
`[environment]`, not a manifest override: nothing is layered under it. `[forge]` rather
than a top-level key, because the GitCode work (the issue repository, #45) needs more
settings of the same kind.

**The fork URL is the project's own `upstream` URL with the namespace segment before the
repository replaced**: `https://gitcode.com/Cangjie/<repo>.git` becomes
`https://gitcode.com/<owner>/<repo>.git`, and the scp form `git@host:Cangjie/<repo>.git`
likewise. The URL is read from the store's `upstream` remote, not the manifest, so a
project the manifest no longer lists still gets its fork. The owner is limited to
letters, digits, `.`, `_` and `-`, since it is spliced into a URL.

**git stays the only place a fork URL is stored.** `cjdev config origin [OWNER]` and
`cjdev init --fork-owner OWNER` record the owner and add `origin` to every store that
has none. An `origin` that already exists and differs is reported with the command that
would change it, and kept: a fork named differently is the user's choice, and replacing
it would make a push land somewhere they did not pick.

**`push` names only `origin`**, refuses an `origin` equal to `upstream`, and rewrites a
branch only under `--force-with-lease`, the lease pinned to the remote-tracking SHA the
run read. The PR link is the first URL the remote printed on its `remote:` lines; with
none, the fork's web page.

Rejected: a URL per project in the config (six facts to keep in sync with git), a
template string such as `https://{host}/{owner}/{repo}.git` (one more syntax for the
same rule), and asking the forge API for the user's forks (needs the API and a token;
#47's business).

## Consequences

A nested namespace (`group/sub/repo`) is forked to `group/<owner>/repo`, which matches
no forge's fork naming. No shipped project has one; a setting that names the full fork
namespace would be the next step if one appears. `init` does not ask for the owner: a
workspace that only reads upstream needs no fork, and every question a wizard asks
needs a flag anyway.
