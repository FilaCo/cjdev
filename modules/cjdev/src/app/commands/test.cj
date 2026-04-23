package cjdev.app.commands

import cli_cj.*

protected let TEST_CLI = commandLine()

@Command[TEST_CLI, help: "Test Cangjie SDK projects."]
private func test() {}
