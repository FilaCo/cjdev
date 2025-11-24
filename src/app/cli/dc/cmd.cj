package cjdev.app.cli.dc

import std.env.exit
import cli.{Arg, ArgMatch, Command}

private let DC_CMD_ABOUT = "Execute the command in the cjdev container"
private let DC_CMD_USAGE = "Usage: cjdev dc [OPTIONS] '[ARGS]...'"
public let DC_CMD = Command("dc")
    .about(DC_CMD_ABOUT)
    .help(DC_CMD_ABOUT)
    .usage(DC_CMD_USAGE)
    .arg(Arg("args").positionalArgsSet(true, 1).help("Args for the command to execute"))
    .action(dcAction)

func dcAction(matches: ArgMatch) {
    println(DC_CMD_USAGE)
    exit(1)
}
