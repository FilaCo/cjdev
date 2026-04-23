package cjdev.app.commands

import cli_cj.*

protected let SYNC_CLI = commandLine()

@Command[SYNC_CLI, help: "Sync all projects to the upstream default branch."]
private func sync() {}
