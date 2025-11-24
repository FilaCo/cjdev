package cjdev.app.cli.init_cmd

import cli.{Arg, ArgMatch, Command}

private let INIT_CMD_ABOUT = "Initialize cjdev environment"
private let INIT_CMD_USAGE = "Usage: cjdev init [OPTIONS]"
public let INIT_CMD: Command = Command("init")
    .about(INIT_CMD_ABOUT)
    .help(INIT_CMD_ABOUT)
    .usage(INIT_CMD_USAGE)
    // TODO: Aliases doesn't work properly in the cli-cj package (in the help message)
    .alias("i")
    .arg(Arg("branch").help("A remote branch for tracking updates").short(r'b'))
    .action(initAction)

func initAction(matches: ArgMatch) {}
