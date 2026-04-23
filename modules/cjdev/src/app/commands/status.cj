package cjdev.app.commands

import cli_cj.*

protected let STATUS_CLI = commandLine()

@Command[STATUS_CLI, help: "Show cjdev environment status."]
private func status() {
}
