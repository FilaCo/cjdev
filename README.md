# cjdev

Cangjie's developer utilities.

## Highlights

- **Easy to use**: Provides a simple and intuitive CLI for building, syncing and uploading Cangjie's projects. Powered by [Typer](https://typer.tiangolo.com/)
- **Containerized**: Wraps environment and dependencies for building Cangjie's projects in a docker container.
- **Optimized**: Uses [Ccache](https://ccache.dev/) and [git-worktree](https://git-scm.com/docs/git-worktree) to reduce build times.

## Installation

Create and activate a virtual environment and then install cjdev:

```bash
pip install cjdev
```

## Features

### Workspaces

- `cjdev init` - create a workspace and fetch the projects it holds.
- `cjdev status` - what the workspace holds: branch sets, projects and their git state.
- `cjdev config show` - the effective configuration: the bundled manifest with the
  workspace's `.cjdev/config.toml` layered over it (`-v` names the layer each value
  came from).

### Branch sets

A branch set is one checkout per project, all on a branch of the same name, gathered
under a single directory named after that branch.

```bash
cjdev branch new fix/parser-ice
cd fix-parser-ice/cangjie_compiler
```

- `cjdev branch new BRANCH_SET` - create one, adopting a branch that already carries the
  name and completing a set that covers only some projects. `-w/--workspace PATH` names
  the workspace to create it in; the default is the cwd, walked up like git.

### Build

Builds happen where you stand: the branch set you are inside is the one that gets
built, and there is no flag for it.

```bash
cd fix-parser-ice/cangjie_compiler
cjdev build                          # the whole SDK, in dependency order
cjdev build stdlib                   # stdlib and everything it needs
cjdev build --from runtime           # runtime and everything that depends on it
cjdev build compiler -p debug        # the other profile, no reconfigure
cjdev build compiler -- --no-tests   # from the flag on, passed to the script
```

- `cjdev build [UNITS...]` - build the named units or projects, with their
  dependencies. One unit at a time: each upstream script already takes the whole
  machine. There is no `--workspace`: the cwd names the branch set too.

Artefacts never land in the worktree. Each unit's scratch directories are symlinked
into `.cjdev/build/<branch set>/<profile>/<unit>/`, so two branch sets never share a
build and switching `-p debug` to `-p release` costs no reconfigure. Output is teed to
`.cjdev/log/<branch set>/<unit>.log` while it runs, so a long build can be tailed.

Every unit installs into one shared `.cjdev/dist/<branch set>/<profile>`, and each unit
builds *with* what the ones before it installed: cjdev sets up the same environment
`source <sdk>/envsetup.sh` would - `CANGJIE_HOME`, `CANGJIE_STDX_PATH`, the SDK's `bin`
directories on `PATH` and its runtime libraries on the library path - so nothing has to
be sourced by hand.

`ccache` is used when it is installed - through a shim directory first on `PATH`,
because the upstream scripts overwrite `CC` and `CXX` with their own lookup.

### Test

### Git/GitCode stuff

## Documentation

The command line reference documentation can be viewed with `cjdev -h`

## License

cjdev is licensed under either of

- MIT License ([LICENSE-MIT](LICENSE-MIT) or http://opensource.org/licenses/MIT)
- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or http://www.apache.org/licenses/LICENSE-2.0)

at your option.
