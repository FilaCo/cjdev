# ADR-0059: A failed build unit cancels what depends on it, not everything after it

Status: accepted, 2026-10-12. Closes #59.

## Context

`cjdev build` ran `Runner(jobs=1, fail_fast=True)` over `build_order()`, so a failure
cancelled every unit after it. That was right while the units were one chain. ADR-0042
added `objc-interop-gen`, which depends on nothing, so it sorts into the first wave,
ahead of `stdlib`. A failure there (its `third_party/tinytoml` clone needs the network,
or the image's libclang does not match) cancelled `stdlib`, `stdx` and `cjpm`, which do
not depend on it.

## Decision

**A failed unit cancels its transitive dependents, and nothing else.** `Work` carries
`needs`, the labels of earlier work that must end DONE, and the build gives each unit
its `depends_on`. The runner stays `fail_fast` for every other caller; Ctrl-C still
cancels everything not started.

Rejected: ordering `objc-interop-gen` after the SDK chain. `build_order()` sorts in
dependency waves, so only a false edge (`depends_on = ["cjpm"]`) would move it, and the
next independent unit would bring the problem back.

## Consequences

One job and submission order are unchanged, so a run with no failure is the same run. A
run with one now builds every unit that does not depend on the failure: a failed
`compiler` still lets `runtime` build. That is only safe while `depends_on` names every
real dependency, which the ordering already relied on.
