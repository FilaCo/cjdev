# ADR-0012: -v changes what is shown, never what is done

Status: accepted, 2026-09-17. Closes #12.

## Context

`-v/--verbose` declared itself "Echo every command" — but in two commands it also
changed execution: `status` and `branch new` computed `jobs = 1 if verbose else
DEFAULT_*`, so a flag named "show me more" silently turned the fan-out sequential. The
serialization was a workaround for an output-ordering problem, and output ordering is
`application/runner.py`'s business, not each command's.

## Decision

`-v` is presentation only, everywhere, as a uniform contract: no command may derive
scheduling, ordering or cancellation from it — no job count, no transcript
serialization. What `-v` adds is defined per command and said in that command's help
("Show more detail."; `config show`: "Show which layer every value came from.").

The ordered transcript survives without serializing the run: a worker never prints
under a fan-out (output is captured per unit and rendered afterwards in manifest
order), so the transcript a fan-out produces is ordered by rule, not by slowing the
fan-out to one job.

## Consequences

The same flag can mean "command echo" in one command and "provenance layers" in
another without either meaning "run me single-threaded" — which is what made `-v` as
the provenance flag in `config show` (ADR-0013) possible at all. A flag whose name
promises presentation is never allowed to change what is done.
