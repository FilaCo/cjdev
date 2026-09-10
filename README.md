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

### Branch sets

A branch set is one checkout per project, all on a branch of the same name, gathered
under a single directory named after that branch.

```bash
cjdev branch new fix/parser-ice
cd fix-parser-ice/cangjie_compiler
```

- `cjdev branch new NAME` - create one, adopting a branch that already carries the name
  and completing a set that covers only some projects.

### Build

### Test

### Git/GitCode stuff

## Documentation

The command line reference documentation can be viewed with `cjdev -h`

## License

cjdev is licensed under either of

- MIT License ([LICENSE-MIT](LICENSE-MIT) or http://opensource.org/licenses/MIT)
- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or http://www.apache.org/licenses/LICENSE-2.0)

at your option.
