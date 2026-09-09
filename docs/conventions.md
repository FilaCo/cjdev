# Conventions

## Names

The code uses one vocabulary verbatim, and these are the words:

| term | means |
| --- | --- |
| **project** | one git repository. The unit of cloning, branching and PR creation |
| **build unit** | one buildable subproject inside a project. A project may hold several; the dependency graph is over units, never over projects |
| **workspace** | a directory tree cjdev manages, marked by the `.cjdev/` it holds |
| **branch set** | one branch name checked out across every project that participates in it |
| **object store** | the bare repository behind a project, fetched once and shared by every worktree |
| **manifest** | the project set and the build-unit graph, as data |
| **executor** | how an external command is run: on the host, or later in a container |

Mixing up **project** and **build unit** is the single easiest way to write a wrong
function: `cangjie_runtime` is one project holding two units, so anything that says "for
each project, build it" is already wrong.

## Comments answer "why", never "what"

The code already says what it does; a comment repeating that is a second copy to keep in
sync, and it goes stale silently. So a comment earns its place only by carrying something
the code cannot: the reason a decision was made, the constraint it satisfies, the
alternative that was rejected and why, or the non-obvious behaviour of something else that
forced this shape.

```python
# No. Restates the line below.
# Flatten the branch set name and join it to the root.
return self.root / flatten_branch_set(branch_set)

# Yes. Explains a constraint that is invisible here.
# `Path` folds `.` away entirely, so a name of "." arrives with no parts at
# all and would otherwise resolve to the parent directory.
```

In tests, "why" is usually what the assertion is protecting against. State it - "two
operations on one object store must not run at once, because git does not serialise them
for us" - so that an assertion which looks arbitrary reads as one with a reason, and it is
obvious what breaks if the behaviour changes.
