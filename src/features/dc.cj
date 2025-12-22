package cjdev.features

import std.argopt.ParsedArguments
import stdx.log.Logger
import cjdev.config.GeneralConfig

public class Dc {
    public Dc(private let generalCfg: GeneralConfig, private let logger_: Logger) {}

    public func execute(args: ParsedArguments): Unit {
        if (args.options.contains("help") || args.options.contains("h")) {
            printHelp()
            return
        }
        println(args.nonOptions)
    }

    private static const DC_USAGE = "Usage: cjdev dc [OPTIONS] -- <COMMAND> [ARGS]..."
    private static let DC_HELP = """
Execute a command in the cjdev container

${DC_USAGE}

Arguments:
  [ARGS]...   Arguments for the command to execute

Options:
  -h, --help      Print help."""

    private func printHelp() {
        println(DC_HELP)
    }
}
