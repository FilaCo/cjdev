package cjdev.app

import cjdev.third_party.cli.{Argument, Command}

protected class CjDevCli {
    static func rootCmd(): Command {
        Command("cjdev")
            .withArgument {
                => Argument("config").withShort(r'c').withLong("config").withDescription("CjDev config file path")
            }
            .withSubcommand(initCmd)
            .withSubcommand(buildCmd)
            .withSubcommand(dcCmd)
            .withSubcommand(testCmd)
            .withSubcommand(gitCmd)
    }

    static func initCmd(): Command {
        Command("init").withDescription("Initialize cjdev environment").withAlias("i").withArgument {
            => Argument("branch")
                .withDescription("A remote branch for tracking updates")
                .withShort(r'b')
                .withLong("branch")
        }
    }

    static func buildCmd(): Command {
        Command("build")
            .withDescription("Build Cangjie's projects")
            .withArgument {
                => Argument("build-type").withDescription("Target build type").withShort(r't').withLong("build-type")
            }
            .withSubcommand {=> Command("sdk").withDescription("Build a complete sdk")}
            .withSubcommand {=> Command("compiler").withAlias("cjc").withDescription("Build compiler")}
            .withSubcommand {=> Command("runtime").withAlias("rt").withDescription("Build runtime")}
            .withSubcommand {=> Command("std").withDescription("Build standard library")}
            .withSubcommand {=> Command("stdx").withDescription("Build standard library extensions")}
            .withSubcommand {=> Command("tools").withDescription("Build tools")}
            .withSubcommand {=> Command("cjfmt").withDescription("Build formatter")}
            .withSubcommand {=> Command("cjpm").withDescription("Build package manager")}
            .withSubcommand {=> Command("lspserver").withAlias("lsp").withDescription("Build language server")}
            .withSubcommand {
                => Command("interop").withAlias("cmp").withDescription("Build cangjie_multiplatform_interop tools")
            }
    }

    static func dcCmd(): Command {
        Command("dc")
            .withDescription("Execute the command in the CjDev container")
            .withUsage("cjdev dc [OPTIONS] -- [COMMAND] [ARGS]...")
            .withArgument {=> Argument("args").withDescription("Arguments for the command to execute")}
    }

    static func testCmd(): Command {
        Command("test")
            .withDescription("Test Cangjie's projects")
            .withArgument {=> Argument("args")}
            .withArgument {
                => Argument("file").withDescription("A testlist file to read from").withShort(r'f').withLong("file")
            }
            .withArgument {
                => Argument("groups").withDescription("A testcase group to run").withShort(r'g').withLong("groups")
            }
            .withArgument {
                => Argument("dump-fail")
                    .withDescription("Create testlist, which stores failed testcases")
                    .withShort(r'd')
                    .withLong("dump-fail")
            }
    }

    static func gitCmd(): Command {
        Command("git")
            .withDescription("Utils for Cangjie's repositories management")
            .withSubcommand {
                => Command("init").withAlias("i").withDescription("Initialize git repos").withArgument {
                    => Argument("branch")
                        .withDescription("A remote branch for tracking updates")
                        .withShort(r'b')
                        .withLong("branch")
                }
            }
            .withSubcommand {
                => Command("sync").withDescription("Sync all repos with upstreams").withArgument {
                    => Argument("sync-origin")
                        .withDescription("Sync origins with the upstreams")
                        .withLong("sync-origin")
                }
            }
            .withSubcommand {
                => Command("switch")
                    .withDescription("Switch to the branch")
                    .withArgument {=> Argument("branch").withDescription("A branch to switch")}
            }
            .withSubcommand {
                => Command("pull-request")
                    .withAlias("pr")
                    .withDescription("Create PRs to upstreams with commited changes")
                    .withArgument {
                        => Argument("title")
                            .withDescription("A title for the pull request")
                            .withShort(r'T')
                            .withLong("title")
                    }
            }
    }
}
