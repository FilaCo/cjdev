package cjdev.app.cli

import std.env.exit
import cli.{Arg, ArgMatch, Command}
import cjdev.app.cli.dc.DC_CMD
import cjdev.app.cli.git.GIT_CMD
import cjdev.app.cli.init_cmd.INIT_CMD

private let CJDEV_CMD_USAGE = "Usage: cjdev [COMMAND] [OPTIONS]"
// TODO: Get from cjpm.toml
private let CJDEV_CMD_ABOUT = "Cangjie's developer utility tool"
public let CJDEV_CMD: Command = Command("cjdev")
    .about(CJDEV_CMD_ABOUT)
    .usage(CJDEV_CMD_USAGE)
    .action(cjdevAction)
    .subcommand(INIT_CMD)
    //.subcommand(BUILD_CMD)
    .subcommand(DC_CMD)
    //.subcommand(TEST_CMD)
    .subcommand(GIT_CMD)

func cjdevAction(_: ArgMatch) {
    println(CJDEV_CMD_USAGE)
    exit(1)
}
