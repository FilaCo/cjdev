package cjdev.features

import std.argopt.ParsedArguments
import stdx.log.Logger

public class Dc {
    public Dc(private let logger_: Logger) {}

    public func execute(args: ParsedArguments): Unit {
    }

    private static const DC_USAGE = "Usage: cjdev dc [OPTIONS] -- <COMMAND> [ARGS]..."
    private static let DC_HELP = """
Execute a command in the cjdev container

${DC_USAGE}

Arguments:
  [ARGS]...   Arguments for the command to execute

Options:
  -V, --version   Print version info and exit
  -v, --verbose   Use verbose output
  -h, --help      Print help."""
}
