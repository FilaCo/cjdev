package cjdev.commands

import std.argopt.{ArgumentSpec, ArgumentMode, ArgumentParseException, parseArguments}
import std.env.exit
import stdx.log.Logger

public class CjDevCommand {
    public CjDevCommand(private let dc_: DcCommand, private let logger_: Logger) {}

    public func execute(args: Array<String>): Unit {
        logger_.trace("executing cjdev command...")
        try {
            let parsed = parseArguments(args, CJDEV_ARGS_SPEC)
        } catch (e: ArgumentParseException) {
            logger_.error("argument parsing failed")
            println(CJDEV_USAGE)
            exit(1)
        }
    }

    private static let CJDEV_ARGS_SPEC = [Full("version", r'V', NoValue), Full("verbose", r'v', NoValue),
        Full("help", r'h', NoValue)];
    private static const CJDEV_USAGE = "Usage: cjdev [OPTIONS] [COMMAND]"
    private static let CJDEV_HELP = """
Cangjie's developer utility tool

${CJDEV_USAGE}

Options:
  -V, --version   Print version info and exit
  -v, --verbose   Use verbose output
  -h, --help      Print help

Commands:
  init, i   Init cjdev environment
  build     Build Cangjie's projects
  test      Test Cangjie's projects
  git       Git utils for Cangjie's repositories management
  dc        Execute a command in the container.
"""
}
