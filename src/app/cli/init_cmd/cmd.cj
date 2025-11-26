package cjdev.app.cli.init_cmd

import cli.{Arg, ArgMatch, Command}
import cjdev.third_party.di.Registry

private let INIT_CMD_ABOUT = "Initialize cjdev environment"
private let INIT_CMD_HELP = "Initialize cjdev environment"
private let INIT_CMD_USAGE = "Usage: cjdev init [OPTIONS]"

public func initCmd(cfg: Registry): Command {
    Command("init")
        .about(INIT_CMD_ABOUT)
        .help(INIT_CMD_HELP)
        .usage(INIT_CMD_USAGE)
        // TODO: Aliases doesn't work properly in the cli-cj package (in the help message)
        .alias("i")
        .arg(Arg("branch").help("A remote branch for tracking updates").short(r'b'))
        .action {matches => initAction(cfg, matches)}
}

private func initAction(cfg: Registry, matches: ArgMatch) {}
