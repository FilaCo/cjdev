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

## What a test may depend on

The decision a command makes must be assertable with nothing available: no git, no network,
no workspace on disk. That is what the pure decide phase is for, and a test that needs a
repository in order to check a decision is testing the wrong layer.

Behaviour that genuinely depends on git is tested against a real git repository in a
`tmp_path`. A fake would only assert what we believe git does, which is the thing most
worth doubting - `worktree add` creating a branch before it fails is exactly the kind of
detail no fake would have reproduced.

Nothing in the suite may touch the network. A test that would need a remote is a sign the
seam is in the wrong place: fetching is a command's job, not an assertion's.

## Commands are listed in README.md

The feature list in `README.md` is where a command is looked for, so it is updated by the
same change that adds the command. One that ships unlisted is one nobody outside this
repository can find.
