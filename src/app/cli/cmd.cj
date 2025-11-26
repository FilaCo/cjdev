package cjdev.app.cli

import std.env.exit
import cli.{Arg, ArgMatch, Command}
import cjdev.app.cli.dc.dcCmd
import cjdev.app.cli.git.gitCmd
import cjdev.app.cli.init_cmd.initCmd
import cjdev.third_party.di.Registry

private let CJDEV_CMD_USAGE = "Usage: cjdev [COMMAND] [OPTIONS]"
// TODO: Get from cjpm.toml
private let CJDEV_CMD_ABOUT = "Cangjie's developer utility tool"
private let CJDEV_CMD_HELP = "Cangjie's developer utility tool"

public func cjDevCmd(reg: Registry) {
    Command("cjdev")
        .about(CJDEV_CMD_ABOUT)
        .help(CJDEV_CMD_HELP)
        .usage(CJDEV_CMD_USAGE)
        .action {_ => cjDevAction()}
        .subcommand(initCmd(reg))
        //.subcommand(BUILD_CMD)
        .subcommand(dcCmd(reg))
        //.subcommand(TEST_CMD)
        .subcommand(gitCmd(reg))
}

func cjDevAction() {
    println(CJDEV_CMD_USAGE)
    exit(1)
}
