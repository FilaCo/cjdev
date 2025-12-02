package cjdev.cli

import std.env.{exit, getCommandLine}
import stdx.log.Logger
import cjdev.util.CommandLauncher
import cli.{Arg, ArgMatch, Command}
import yadi.{Registry, RegistryBuilder}

let DC_CMD_LABEL: String = "cjdev.command.dc"
private let DC_CMD_NAME = "dc"
private let DC_CMD_ABOUT = "Execute the command in the cjdev container"
private let DC_CMD_HELP = "Execute the command in the cjdev container"
private let DC_CMD_USAGE = "Usage: cjdev dc [OPTIONS] '[ARGS]...'"
private let ARGS_HELP = "Args for the command to execute"

func addDcCommand(builder: RegistryBuilder): RegistryBuilder {
    builder
        .addTransient(DC_CMD_LABEL) {
            reg: Registry => Command(DC_CMD_NAME)
                .about(DC_CMD_ABOUT)
                .help(DC_CMD_HELP)
                .usage(DC_CMD_USAGE)
                .action {_ => dcAction(reg.get<Dc>())}
        }
        .addLazy {reg: Registry => Dc(reg.get<CommandLauncher>(), reg.get<Logger>("cjdev.logger.global"))}
}

class Dc {
    public Dc(private let launcher: CommandLauncher, private let logger: Logger) {}

    public func buildContainer() {}

    public func runCmd(args: Array<String>) {
    }
}

private func dcAction(dc: Dc) {
    // dc.runCmd(matches.getStringArray("args"))
}
