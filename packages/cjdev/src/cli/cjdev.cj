package cjdev.cli

import std.env.exit
import cli.{Arg, ArgMatch, Command}
import yadi.RegistryBuilder

public let CJDEV_CMD_LABEL: String = "cjdev.command.cjdev"
private let CJDEV_CMD_NAME = "cjdev"
private let CJDEV_CMD_ABOUT = "Cangjie's developer utility tool"
private let CJDEV_CMD_HELP = "Cangjie's developer utility tool"
private let CJDEV_CMD_USAGE = "Usage: cjdev [COMMAND] [OPTIONS]"

public func addCjDevCmd(builder: RegistryBuilder): RegistryBuilder {
    builder.addTransient(CJDEV_CMD_LABEL) {
        reg => Command(CJDEV_CMD_NAME)
            .about(CJDEV_CMD_ABOUT)
            .help(CJDEV_CMD_HELP)
            .usage(CJDEV_CMD_USAGE)
            .action {_ => cjDevAction()}
            .subcommand(reg.get<Command>(DC_CMD_LABEL))
    }
}

private func cjDevAction() {
    println(CJDEV_CMD_USAGE)
    exit(1)
}
