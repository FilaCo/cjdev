package cjdev.app

import cli_cj.*
import cjdev.app.commands.*

protected let CLI = commandLine()
    .add(INIT_CLI)
    .add(STATUS_CLI)
    .add(SWITCH_CLI)
    .add(SYNC_CLI)
    .add(BUILD_CLI, name: "build", help: "Build Cangjie SDK projects.")
    .add(TEST_CLI)
    .add(PR_CLI)

@Callback[CLI, help: "Cangjie SDK developer utils."]
private func cjdev() {
}
