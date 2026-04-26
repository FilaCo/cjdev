package cjdev.app.commands

import cli_cj.*

protected let INIT_CLI = commandLine()

@Command[INIT_CLI, name: "init", help: "Init cjdev environment."]
private func initCmd() {
}
