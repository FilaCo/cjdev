package cjdev.app.cli.git

import std.env.exit
import cli.{Arg, ArgMatch, Command}
import cjdev.app.config.CjDevConfig

private let GIT_CMD_ABOUT = "Utils for Cangjie's repositories management"
private let GIT_CMD_HELP = "Utils for Cangjie's repositories management"
private let GIT_CMD_USAGE = "Usage: cjdev git [COMMAND] [OPTIONS]"

public func gitCmd(cfg: CjDevConfig) {
    Command("git")
        .about(GIT_CMD_ABOUT)
        .help(GIT_CMD_HELP)
        .usage(GIT_CMD_USAGE)
        .action {matches => gitAction(cfg, matches)}
}

// .subcommand(
//     Command("init")
//         .alias("i")
//         .help("Initialize git repos")
//         .arg(Arg("branch").help("A remote branch for tracking updates").short(r'b'))
//         .action {argMatch => println("hello, git init!")})
// .subcommand(
//     Command("sync")
//         .help("Sync all repos with upstreams")
//         .arg(Arg("sync-origin").help("Sync origins with the upstreams")))
// .subcommand(Command("switch").help("Switch to the branch").arg(Arg("branch").help("A branch to switch")))
// .subcommand(
//     Command("pull-request")
//         .alias("pr")
//         .help("Create PRs to upstreams with commited changes")
// .arg(Arg("title").help("A title for the pull request").short(r'T')))

private func gitAction(cfg: CjDevConfig, matches: ArgMatch) {
    println(GIT_CMD_USAGE)
    exit(1)
}
