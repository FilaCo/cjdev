# ADR-0052: The java interop builds as two units, and the generator's JDK sources are scratch

Status: accepted, 2026-10-12. Closes #52.

## Context

ADR-0042 gave `cangjie_multiplatform_interop` its objc units and left `java/`
without any, so `java.lang`, `java.internal`, `library-loader.jar` and
`java-mirror-gen.jar` were never in the dist. One script, `java/build/build.py`,
builds both, and exits at import without `JAVA_HOME` and `CANGJIE_HOME`. Its
interoplib switch differs from objc's: `build --target-lib` builds it, while
`build --target` is a triple for clang and cjc. The generator is built by `ant`
against BiShengJDK 21's javac: the script clones it into
`third_party/bishengjdk-21`, copies a subset into `third_party/jdk`, patches the
copy, and `rmtree`s the clone. Upstream ignores none of that, nor the jar or
ant's `build/`.

## Decision

**Two units, `java-interoplib` and `java-mirror-gen`**, as for objc: one argv
cannot be both modes, and their scratch is disjoint.

**The generator's JDK sources are scratch, not a `third_party` link.** ADR-0027
links a fetched commit where upstream looks, which holds only where nothing
wipes the path. Here the script `rmtree`s the clone, which Python refuses on a
link, and the copy is its own patched output rather than a commit. As scratch
both are excluded from git and keyed by profile, so the clone runs once per
branch set, environment and profile.

**The image carries `openjdk-21-jdk-headless` and `ant`, and sets JAVA_HOME** to
a link to the JDK, since the package's directory names the architecture. 21
rather than 17 because that is the javac the generator compiles. A host build
needs its own JDK and JAVA_HOME.

## Consequences

A second profile, or a new branch set, clones BiShengJDK again. A clone killed
midway is trusted by the next run of that profile, the shape of #27. The project
stays in no group: a host rarely has GNUstep or a JDK.
