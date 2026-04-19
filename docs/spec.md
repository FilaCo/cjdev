# Cjdev specification

## Introduction

Cjdev is an utility that aims to assist Cangjie SDK developers with their day-to-day routines, e.g. building projects, creating PRs, etc. To achieve that, Cjdev provides a simple-to-use CLI tool with the same name.
It is argued that developers tend to make custom Bash/Python scripts to handle such tasks, because there is no ideal solution. That's why Cjdev leaves a reasonable space for its scripts customization.

This document's purpose is to specify what issues of the users Cjdev resolves and how does it resolve them. In other words, it is some sort of technical specification with functional (answer to the "what" question) and non-functional (answer to the "how" question) requirements.

## Glossary

1. Cjdev - system under development.
2. Cangjie SDK - Cangjie compiler, runtime, standard library, tools combined together.
3. cjc - Cangjie compiler.
4. std - Cangjie standard library.
5. rt - Cangjie runtime.
6. cjpm - Cangjie package manager.
7. LSPServer - Cangjie LSP server.
8. PR - pull request on GitCode.
9. GitCode - is a website that hosts Cangjie SDK projects source code.

## Functional requirements

The main goal of Cjdev is to assist Cangjie SDK developers with their contributions. Here is the list of functional requirements that Cjdev conforms to in order to reach the goal:

1. Cjdev must allow getting Cangjie SDK projects source code.
2. Cjdev must allow building Cangjie SDK. It includes building its projects one by one, or all together.
3. Cjdev must allow making changes in Cangjie projects source code.
4. Cjdev must allow testing Cangjie SDK projects.
5. Cjdev must allow creating PRs into Cangjie GitCode projects.

## Non-functional requirements

TBD
