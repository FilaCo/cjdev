package cjdev.app.cli.dc

import std.env.exit
import cli.{Arg, ArgMatch, Command}
import cjdev.app.config.CjDevConfig

private let DC_CMD_ABOUT = "Execute the command in the cjdev container"
private let DC_CMD_HELP = "Execute the command in the cjdev container"
private let DC_CMD_USAGE = "Usage: cjdev dc [OPTIONS] '[ARGS]...'"

public func dcCmd(cfg: CjDevConfig): Command {
    Command("dc").about(DC_CMD_ABOUT).help(DC_CMD_HELP).usage(DC_CMD_USAGE).action {matches => dcAction(cfg, matches)}
}

private func dcAction(cfg: CjDevConfig, matches: ArgMatch) {
    println(DC_CMD_USAGE)
    exit(1)
}
