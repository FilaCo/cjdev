package cjdev.app.cli.git

import cli.{Arg, ArgMatch, Command}

public let GIT_CMD: Command = Command("git").help("Utils for Cangjie's repositories management").action(gitAction)
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

private func gitAction(matches: ArgMatch) {
}
