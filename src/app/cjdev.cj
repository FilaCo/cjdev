package cjdev.app

import cli.{Command, Arg, ArgAction, ArgMatch}

public class CjDev {
    public func run(): Unit {
        ROOT.build()
    }

    private static let INIT = Command("init")
        .help("Initialize cjdev environment")
        .alias("i")
        .arg(Arg("branch").help("A remote branch for tracking updates").short(r'b'))

    private static let BUILD = Command("build")
        .help("Build Cangjie's projects")
        .arg(Arg("build-type").help("Target build type").short(r't'))
        .subcommand(Command("sdk").help("Build a complete sdk"))
        .subcommand(Command("compiler").alias("cjc").help("Build compiler"))
        .subcommand(Command("runtime").alias("rt").help("Build runtime"))
        .subcommand(Command("std").help("Build standard library"))
        .subcommand(Command("stdx").help("Build standard library extensions"))
        .subcommand(Command("tools").help("Build tools"))
        .subcommand(Command("cjfmt").help("Build formatter"))
        .subcommand(Command("cjpm").help("Build package manager"))
        .subcommand(Command("lspserver").alias("lsp").help("Build language server"))
        .subcommand(Command("interop").alias("cmp").help("Build cangjie_multiplatform_interop tools"))

    private static let DC = Command("dc")
        .help("Execute the command in the CjDev container")
        .usage("cjdev dc [OPTIONS] -- [COMMAND] [ARGS]...")
        .arg(Arg("args").help("Args for the command to execute"))

    private static let TEST = Command("test")
        .help("Test Cangjie's projects")
        .arg(Arg("args"))
        .arg(Arg("file").help("A testlist file to read from").short(r'f'))
        .arg(Arg("groups").help("A testcase group to run").short(r'g'))
        .arg(Arg("dump-fail").help("Create testlist, which stores failed testcases").short(r'd'))

    private static let GIT = Command("git")
        .help("Utils for Cangjie's repositories management")
        .action {argMatch => println("Hello, git!")}
        .subcommand(
            Command("init")
                .alias("i")
                .help("Initialize git repos")
                .arg(Arg("branch").help("A remote branch for tracking updates").short(r'b'))
                .action {argMatch => println("hello, git init!")})
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

    private static let ROOT = Command("cjdev")
        .arg(Arg("config").short(r'c').help("CjDev config file path"))
        .action {argMatch => println("Hello, world!")}
        //.subcommand(INIT)
        //.subcommand(BUILD)
        //.subcommand(DC)
        //.subcommand(TEST)
        .subcommand(GIT)
}
