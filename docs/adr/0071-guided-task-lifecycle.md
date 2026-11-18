# ADR-0071: A task keeps the same branch set when an experiment is published

Status: accepted, 2026-11-18. Closes #71.

## Context

A developer may know the upstream issue before starting, file one while
starting, or begin with an experiment. Issue templates belong to the home
project and a workspace can have object stores with no task checkouts yet.

## Decision

Read new-issue forms from the home project's upstream default branch in the
workspace's object store. Use the issue number and title to suggest the branch
name. When an experiment acquires an issue during publication, record the issue
on its existing branch set. Each changed project's PR carries the issue URL.

Completion owns local task state. Published fork branches can still be used by
reviewers or other workspaces, so their lifetime belongs to the fork owner.
