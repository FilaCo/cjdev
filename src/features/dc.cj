package cjdev.features

import std.collection.ReadOnlyMap
import std.process.{execute, launch}
import stdx.log.Logger
import cjdev.utils.CommandLauncher

public class Dc {
    public Dc(private let launcher: CommandLauncher, private let logger_: Logger) {}

    public func execute<OptionsMapT>(options: OptionsMapT, nonOptions: Array<String>): Unit where OptionsMapT <: ReadOnlyMap<String,
    String> {
        if (options.contains("help") || options.contains("h")) {
            printHelp()
            return
        }
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
