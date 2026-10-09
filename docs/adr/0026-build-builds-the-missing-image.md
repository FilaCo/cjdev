# ADR-0026: cjdev build builds the missing image itself, unless told to refuse

Status: accepted, 2026-10-09. Closes #26.

## Context

In container mode the build reads the host from the image (ADR-0021). With no image
for the current Dockerfile hash that read failed, and the run stopped with the remedy
`cjdev env build`. So the first build on every fresh machine failed, taught a command
and cost a second invocation. The recorded reason was to avoid "quietly building
minutes of image in the middle of something else".

There is no choice in that image for the caller to make: the Dockerfile ships with
cjdev and the tag is its hash. What the refusal protected against was surprise and
cost, not a wrong decision.

## Decision

**A missing image is a precondition `build` satisfies itself**, through the same path
`env build` takes. Absence is asked with `image ls --quiet <tag>`, a read: an empty
answer is the absence, where a failed `image inspect` would have to be told from a dead
daemon by the wording of its error. Docker and podman behave the same.

**It is visible, never quiet.** The image build is its own row in its own display, and
its own `env build` entry in the workspace log, so the log reads as the two commands a
caller would have typed. A dry run prints the image build and builds nothing; it does
not plan the units, because the plan reads the image's `PATH` and ccache label and
there is no image to read them from.

**`image = "build" | "refuse"` in `[environment]`**, default `build`. `refuse` keeps
the old refusal, for CI and for any workspace where a missing image is a diagnosis
someone wants to see rather than a cost someone wants paid.

Rejected: folding the image build into the build's own log entry (it would not replay
by hand as one command), and a `provision_image` key (`image` sits beside `mode` and
`runtime` and names what is missing).

## Consequences

A fresh machine needs one command. A dry run with no image shows less than one with
an image, because the units are planned from it. A dead daemon is still its own
failure with its own remedy: nothing starts it.
