# ADR-0042: The objc interop builds as two units, keyed by a `{target}` token

Status: accepted, 2026-10-09. Closes #42. Supersedes, in part, ADR-0017: its four tokens.

## Context

`cangjie_multiplatform_interop` was cloned and branched but built nothing, so
`objc.lang` / `objc.internal` and `ObjCInteropGen` were never in the dist and the ObjC
LLT could not run. One upstream script, `objc/build/build.py`, builds both: with
`--target <target>` the interoplib, installed under `<target>_cjnative`; without it
the generator. On Linux the interoplib's glue is compiled against GNUstep, and the
interop calls libobjc2's API. Most workspaces never clone the project.

## Decision

**Two units, `objc-interoplib` and `objc-interop-gen`**, because one argv cannot be
both modes. Their scratch paths are disjoint: they share a directory, and a path two
units move would meet the other's directory with no marker.

**A fifth token, `{target}`**, the build machine's `linux_x86_64`. The interoplib
needs it on its command line and the manifest serves both architectures; a literal
would be wrong on one, and `extra_args` would make every workspace retype it.

**A selection nobody named is narrowed to the projects the branch set holds** - bare
`cjdev build` and `--from`. Otherwise every workspace without the interop project
would stop building. A kept unit's dependencies stay even when absent, so the refusal
names the missing project; a named unit is refused as before.

**The image builds libobjc2, gnustep-base and gnustep-corebase from pinned sources.**
Ubuntu's gnustep-base sits on gcc's libobjc, which lacks the API. ObjCInteropGen
links the system libclang, as its Readme says for Ubuntu, not the LLVM the compiler
unit builds: that would tie it to the compiler's scratch.

## Consequences

298 of the 300 ObjC LLT cases pass in the container; the other 2 link their
executable without `-lcjbase`, and GNU ld refuses. The project stays in no group: on a
host without GNUstep the interoplib fails. ObjCInteropGen clones `third_party/tinytoml`
inside upstream's build, the shape of #27. Java's units are #52.
