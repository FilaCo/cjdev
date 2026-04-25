# Cjdev concept document

This document describes the core ideas behind the Cjdev project.

## What Cjdev is?

Cjdev is a CLI utility that assists Cangjie SDK developers with their daily routines, e.g. getting projects source code, building and testing them, etc. Cjdev main goal is to eliminate all unnecessary PITA steps of the contribution workflow to allow the engineers to focus on things that are **really** important.

## Why it exists?

The Cangjie programming language SDK is not a single project. It's built from several Git repositories, which are linked via GitCode platform. However, during local development, it's an engineer responsibility to properly organize each repository, open issue, link PRs to the issue, etc.
Contributors today compensate for the absence of a unifying tool with personal shell or Python scripts, which suffer from duplicated effort, divergent conventions, and fragile assumptions about workspace layout.

Three workflows are particularly painful:

- **Multi-repo, multi-project builds.** Each buildable project exposes a `build.py` script with a shared but informal convention. Dependencies between projects form a DAG that crosses repository boundaries - the standard library lives in `cangjie_runtime` but depends on the compiler in `cangjie_compiler`. Building the whole SDK therefore means `cd`-ing into each project in the correct dependency order and invoking the right `build.py` incantation, repeatedly.

- **Reproducible toolchain.** SDK builds depend on specific tooling versions - cjc, for example, requires Clang 15 and cannot be compiled with newer versions. Today each contributor arranges their own toolchain, which is brittle.

- **Coordinated pull requests.** A non-trivial change often spans more than one project - for instance, a new standard library API that requires a compiler tweak and, of course, a couple of tests. The contributor opens a tracking issue in `cangjie_compiler`, opens one PR per affected project plus `cangjie_test` project, cross-links each PR to the tracking issue, manually fills horrible PR template, triggers CI via a `start build` comment and monitors review and merge state across the set. This is done by hand today, with no single surface showing the aggregate state of the change.

## Core ideas

Cjdev foundation stands on the following ideas:

### Repositories and projects

Some Cangjie SDK projects live in the same git repositories, for instance "Cangjie Runtime" and "Cangjie Standard Library" share the same `cangjie_runtime` repository. That's the reason why Cjdev separates the concepts of project and repository.

A **repo** is one of the following Cangjie SDK git repositories:

1. [cangjie_compiler](https://gitcode.com/Cangjie/cangjie_compiler.git)
2. [cangjie_runtime](https://gitcode.com/Cangjie/cangjie_runtime.git)
3. [cangjie_stdx](https://gitcode.com/Cangjie/cangjie_stdx.git)
4. [cangjie_tools](https://gitcode.com/Cangjie/cangjie_tools.git)
5. [cangjie_multiplatform_interop](https://gitcode.com/Cangjie/cangjie_multiplatform_interop.git)
6. [cangjie_test](https://gitcode.com/Cangjie/cangjie_test.git)
7. [cangjie_test_framework](https://gitcode.com/Cangjie/cangjie_test_framework.git)

> 6 and 7 actually are not the parts of Cangjie SDK, but they are essential for the e2e testing purposes.

A **project** is a specific buildable component living at a particular path inside a repository. The relationship is one-to-many: a repository may host multiple projects, but every project belongs to exactly one repository. Cross-repository Git operations (clone, fetch, push, worktree) act on repositories; build operations (build, install, clean) act on projects.

`cangjie_test` and `cangjie_test_framework` is a bit special projects, because they don't have any buildable artifact.

Another worth-noting thing about the projects is that they depend on each other during the building procedure. Here is the table that strives to define the DAG on it:

| Repository         | Project | Path in repository | Depends on                 |
|--------------------|---------|--------------------|----------------------------|
| `cangjie_compiler` | `cjc`   | `.`                | —                          |
| `cangjie_runtime`  | `rt`    | `runtime`          | —                          |
| `cangjie_runtime`  | `std`   | `stdlib`           | `cjc`, `rt`                |
| `cangjie_stdx`     | `stdx`  | `.`                | `cjc`, `rt`, `std`         |
| `cangjie_tools`    | `cjpm`  | `cjpm/build`       | `cjc`, `rt`, `std`, `stdx` |

### Topics

A **topic** is a named, cross-repository unit of work. It groups:

- A branch name per affected repository.
- A tracking issue in one of the affected repositories.
- Zero or more PRs, one per repository whose branch has diverged from its upstream default branch.

Topics are the primary object Cjdev manipulates.
Each topic has a filesystem presence at `workspace/topics/<topic>/`, containing Git worktrees of the repos the topic touches.

### Backend

A **backend** is an environment in which Cjdev performs its build and test commands. Two backends are specified:

- **Host backend.** Commands run directly on the host. The contributor is responsible for providing the toolchain. This is the default.
- **Container backend.** Commands run inside an ephemeral container with a toolchain fixed by the bundled Dockerfile. The container is torn down after each invocation; all persistent state lives on the host and is bind-mounted into the container.

## Use-case walkthrough
