package cjdev.app.commands

import cli_cj.*

protected let SWITCH_CLI = commandLine()

@Command[SWITCH_CLI, help: "Switch projects to the specified branch."]
private func switch() {}
