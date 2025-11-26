package cjdev.cli

import std.env.exit
import cjdev.util.CommandExecutor
import cli.{Arg, ArgMatch, Command}
import yadi.{Registry, RegistryBuilder}

let DC_CMD_LABEL: String = "cjdev.command.dc"
private let DC_CMD_NAME = "dc"
private let DC_CMD_ABOUT = "Execute the command in the cjdev container"
private let DC_CMD_HELP = "Execute the command in the cjdev container"
private let DC_CMD_USAGE = "Usage: cjdev dc [OPTIONS] -- [ARGS]..."

public func addDcCmd(builder: RegistryBuilder): RegistryBuilder {
    builder.addTransient(DC_CMD_LABEL, {
        reg => Command(DC_CMD_NAME)
            .about(DC_CMD_ABOUT)
            .help(DC_CMD_HELP)
            .usage(DC_CMD_USAGE)
            .action {_ => dcAction(reg)}
    })
}

class Dc<T> where T <: CommandExecutor {
    public Dc(private let executor: T, private let logger: Logger) {}
}

private func dcAction(reg: Registry) {
    println(DC_CMD_USAGE)
    exit(1)
}
