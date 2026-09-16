# Architecture

`cjdev` orchestrates external processes and owns no business rules, so the core is
deliberately thin: data and pure functions.

## Layers

The import direction is the point of them: `domain` depends on nothing of ours except
`errors`, `application` depends on `domain` and on its own ports, `infra` and `cli`
depend inwards. An `import` from `domain` into `infra` is a bug, not a shortcut.

`errors.py` sits *below* `domain` - it imports nothing at all, so every layer may raise
from it. It is the only module with that position.

```text
src/cjdev/
  __init__.py              # main(); the console script entry point
  bootstrap.py             # composition root - assembles executors and use cases
  errors.py                # error hierarchy → exit codes and error codes

  domain/                  # pure: no subprocess, no filesystem, no network
    manifest.py            # Project, BuildUnit and the build graph
    layout.py              # workspace path algebra, parameterised by root
    branch.py              # whether a string may be a git branch name
    state.py               # branch / SHA / dirty / ahead-behind

  application/             # orchestration and policy; one module per command
    ports.py               # Executor, FileSystem, Prompt - nothing else
    runner.py              # fan-out, -j, output ordering, cancellation
    workspace.py           # finding the workspace root, and what it holds
    init_workspace.py      # `cjpm init` use case file
    ...                    # other use case files

  infra/                   # the only layer that touches the outside world
    executor/              # build_executor(); hides the decorator order
      host.py  trace.py  dry_run.py
    git.py                 # argv for git, and parsing its output
    filesystem.py          # the real tree, or the one that only describes itself
    prompt.py              # questionary, or the refusal to ask
    journal.py             # the workspace log, .cjdev/log/cjdev.log
    config.py              # manifest loading and the schema-version gate
    data/default_manifest.toml      # the shipped manifest; travels in the wheel

  cli/                     # Typer wiring
    _context.py            # the typed Context
    _console.py            # one Console, and the marks for ok/failed/cancelled
    _progress.py           # the live display, and per-unit output capture
    _output.py             # the --json envelope, and which mode a run is in
    _render.py             # the terminal report, and the payload --json carries
    init.py                # `cjpm init` command entrypoint
    ...                    # other command entrypoints
```

## The entry point

`[project.scripts]` names `main` in `src/cjdev/__init__.py`, not the Typer app itself:
`main()` wraps it so an expected failure leaves as a message and an exit code rather than
a traceback. Adding subcommands needs no change to `pyproject.toml`.

```python
def main() -> None:
    try:
        cli()
    except CjdevError as exc:
        ...
```

## The composition root

`bootstrap.py` is the only module that knows which abstraction is which concrete class;
everything above it is handed its collaborators. It lives outside `cli/` so that a test,
and later a CI entry point, can assemble the same graph without going through Typer.

`Container` carries two mutable fields, `emit` and `report_step`, because a command only
learns where its output should go once it has built the display that collects it. **They
are read when a collaborator is built, not when it is used**, and so is the journal
handle. That makes the order inside a command body load-bearing:

```python
progress = ConsoleProgress(...)
ctx.obj.emit = progress.emit          # first
ctx.obj.report_step = progress.step
ctx.obj.journal(root, argv)           # then, for a mutating command
use_case = ctx.obj.init_workspace(…)  # only now
```

Set `emit` after building the use case and output goes to `print` instead of the display;
skip `journal()` and the run is simply not logged. Neither fails, both go quiet, which is
why the order is written down rather than left to be rediscovered.

## Use cases are gather → decide → apply

A use case reads the world, computes a decision purely, then applies it. The pure middle
phase is what makes preflight, `--dry-run` and the tests possible at all: the decision can
be asserted on without git, network or containers. Complex flows are a sequence of such
phases, not one big pure function - resist making the whole command pure, and resist
interleaving the three.

## Concurrency lives in `application/runner.py`

Commands hand the runner a list of independent units of work; they never spawn threads
themselves. The job count, output ordering, cancellation and the per-unit summary are
implemented once, there. Two units touching the same object store must not run
concurrently - the fan-out key is the project for git work and the build unit for builds.

No command exposes the job count: everything that can overlap does, at the default its
use case names. Whether that stays true is an open question, and a use case that wants a
different answer takes `jobs` as an argument, so the fan-out is real either way - one job
is strictly sequential in manifest order.

`status` and `branch new` pass one job under `-v`, because a transcript interleaved by
the scheduler is not a transcript.

## Ports, and what earns one

A port is earned by a second implementation that will actually exist. There are three:
`Executor` (host today, container next), `FileSystem` (real, or dry-run) and `Prompt` (a
terminal, or a pipe/`--dry-run`). `Forge` will be the fourth once the gitcode work starts; it
is absent from `ports.py` rather than stubbed, because an empty protocol tells a reader
nothing and invites guessing.

Note what the three have in common: their second implementation is a flag the user passes,
not a seam invented for tests. **If a proposed port's second implementation only ever
appears in a test file, it is not a port.**

`FileSystem` earned its place the hard way. `init --dry-run` created the workspace it was
supposed to only describe, because the executor covers subprocesses and `Path.mkdir` is
not one. Anything that changes the tree goes through the port; anything that only reads it
does not, since a probe has to be real or the plan is built on guesses.

Git in particular is **not** a port. Driving the real `git` binary is a commitment made
once - worktrees, `rerere`, `--force-with-lease` and the credential helpers all behave as
documented only there - and that binary is reached through `Executor` already; a second
abstraction over the same subprocess is a tax with no payer. `infra/git.py` builds argv and
parses output, and is tested against real git in a `tmp_path`.

## The workspace log

Every mutating command opens `.cjdev/log/cjdev.log` before it builds its use case, and
`RecordingExecutor` writes one complete line per external command - status, duration,
argv, cwd - plus the output of anything that failed. It is always on, because the question
it answers ("what did that actually run?") is only ever asked afterwards, and `-v` has to
be turned on in advance. A dry run records nothing; read-only commands do not open it.

Writing to it is best-effort: a full or read-only disk must never be the reason a command
fails, so `CommandJournal` swallows its own errors.

## Terminal output

`rich` renders it. Three rules:

1. **Marks, not emoji**: `✓`, `✗` and `-` say how something ended, line up in a column and
   mean the same thing to everyone; a picture of a rocket does neither.
2. **A worker never prints**: under a fan-out the order things happen in belongs to the
   scheduler, and the transcript is not allowed to, so command output is captured per unit
   and rendered afterwards in manifest order. The live display is the one thing allowed to
   be concurrent, and it draws only status.
3. **stdout is the report, stderr is everything about it**: the `-v` transcript, the
   progress fallback and errors all go to `diagnostics`, so that `--json` stays a document
   something else can parse.

A long-running command answers three questions: what it is doing, how long it has been
doing it, and how much longer. `_progress.py` shows all three; the per-unit step comes
from `Command.what` through `StepExecutor`, so adding a step to a new command means
labelling the command.

## The machine surface

`--json` is a contract with something that is not a person, so it is shaped like one.
Every command that has it prints the same envelope - `schema`, `command`, `ok`, `data`,
`errors`. Fields are added and never repurposed; anything else bumps the number in
`cli/_output.py`.

Today that is `status` and `branch new`. `init` has no `--json`, because the machine-facing way
to answer its wizard is still an open question, and an envelope with no way to supply the
project set would only look like a working non-interactive path. The envelope is where it
lands when that is settled; nothing else changes.

Three rules follow, and they are why `_output.py` exists instead of each command reaching
for `json.dumps`:

1. **The document is written with `print`, never through `rich`.** A renderer that knows
   about terminal width, colour and markup has no business near something a parser is
   about to read, and "remember to pass `markup=False`" is not a guarantee.
2. **Stdout carries the document.** Under `--json` the progress display and the transcript
   move to stderr; a command asks `out.display` which console it is writing to rather than
   deciding for itself.
3. **A failure goes inside the envelope, not beside it.** `main()` renders whatever
   escapes through `Output.failure`, which is why the mode is module state: by then
   Typer's context is gone, and `_output.py` is the only thing left that knows how the
   command meant to report. A command that already printed its own document - `status`
   reporting five readable projects and one that is not - keeps it, because one document
   per run beats a second one contradicting it.

`begin()` is called first thing in a command body, before anything can fail. It names the
command *and* resets the mode, which matters even for a command with no `--json`: the mode
is module state, so an earlier invocation in the same process would otherwise still be in
force.

Every failure carries a **code** as well as an exit code, and they answer different
questions: the exit code says which of the four kinds it was, the code says which failure
it was and survives someone rewording the message. `errors.py` documents both in one
table. Where a failure has a fix that can be named, it goes in `remedy` and both
renderings print it - but an invented remedy is worse than a null one, because the caller
it exists for cannot tell a good guess from a bad one.

## Questions, answers, and consent

**Settings and consent are different questions, and one flag must never answer both.**
Ticking a project set says nothing about agreeing to delete what is no longer in it, and a
flag that did both would arm deletions in every script that only wanted to skip a wizard.

`Container.prompt()` keeps them apart: `interactive` is whether to ask, `assume_yes` is the
answer to give when nobody is asked.

Nothing supplies consent from the command line today, and nothing needs to. `--dry-run`
is the only thing that answers on the caller's behalf, and it may because it removes
nothing; everything else asks at a terminal or refuses.

| command | asks | flags |
| --- | --- | --- |
| `init` | a wizard for the project set, then consent if the answer drops one | none; `--dry-run` asks nothing |
| `status` | nothing | none |
| `branch new` | nothing - the whole input is the name | none |

`clean` - emptying a workspace, object stores and all - was the third row until its name
became the problem: build scripts spell "remove the artefacts" `clean` too, and the two
readings differ by hours of refetching. A name that means the more destructive of two
plausible things is worse than an absent one, so the command is gone until it has a name
of its own. The flag that answers a confirmation goes with it: whatever it turns out to
be, it must answer the confirmation and nothing else.

`init` therefore **needs a terminal**. With no TTY and no `--dry-run` it refuses with exit
3 rather than picking a project set nobody chose or blocking on a stdin nobody will write
to. The flag that answers the wizard from a script is deliberately absent until its shape
is decided; when it arrives, the rule it has to satisfy is that **every question a wizard
asks needs a flag that answers it**, and "take the defaults" is not that flag - defaults
are what a first-time caller has none of.

## File or folder?

**A folder is warranted when there is something to hide.** Its `__init__.py` is a decision
about what does *not* escape. If that file would just re-export everything inside, the
folder bought nothing and cost a segment on every import.

`infra/executor/` passes the test: the caller gets `build_executor()` and never learns that
the stack is dry-run over logging over host. `infra/git.py` is a single file for the same
reason - a folder holding one module is just a module with extra steps.

CLI modules are always files, never packages. A CLI module is Typer wiring; five
subcommands are ~120 lines of the same shape, which reads better in one file than in five.
The inverse is the useful rule: **if a CLI module grows enough to want a folder, logic has
leaked into it that belongs in `application/`** - the folder would hide a layering
violation rather than organise anything.

A related smell, and one this project actually grew: a command file with one subcommand per
manifest entry. An early `build.py` was thirteen near-identical stubs against a manifest of
four units, and the two had already drifted. One command that takes its names *from* the
manifest cannot drift, and gets completion for free. **If you are about to write the same
command shape N times, the N belongs in data.** (That command is gone for now: a command
that always fails is worse than an absent one, because it fills `--help` and shell
completion with something nobody can use. It comes back when there is a builder behind it.)

## TOML

`tomlkit` is the only TOML library used, for reading and writing alike. `tomllib` would
cost nothing, but it is read-only and 3.11+, and `cjdev` writes TOML: `init` creates
`.cjdev/config.toml`, and a `config set` will write into it later. Comment and key-order
preservation is not a nicety here - `config.toml` is a file the user edits by hand *and*
`cjdev` writes into, so regenerating it would throw away their comments and ordering every
time.

The price is that `tomlkit` returns `TOMLDocument`, not `dict`. Keep it inside `infra/`:
`config.py` converts to the `domain/` dataclasses at the boundary, and no `TOMLDocument`
reaches `application/` or `domain/`.

Be aware of what that file is today: `init` writes it, and **nothing reads it back**. The
manifest comes from the copy bundled in the wheel, every time. Layering a workspace's
overrides on top of it is the next thing `infra/config.py` gains, and until then the file
is a placeholder rather than configuration.

## Bundled data

`infra/data/` is a plain directory, not a package. Reach it through the anchor package:

```python
from importlib.resources import files

files("cjdev.infra") / "data" / "default_manifest.toml"
```

`uv_build` ships non-Python files under the module root, so the TOML lands in the wheel. It
is still worth a test that loads it through `importlib.resources` rather than from the
working tree - otherwise a packaging regression shows up only for users.
