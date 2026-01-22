package cjdev.features

import std.collection.ReadOnlyMap
import stdx.log.Logger

public class Build {
    public Build(private let logger_: Logger, private let launcher_: CommandLauncher) {}

    public func execute<OptionsMapT>(options: OptionsMapT, nonOptions: Array<String>): Unit where OptionsMapT <: ReadOnlyMap<String,
    String> {
        if (options.contains("help") || options.contains("h")) {
            printHelp()
            return
        }

        let buildType = options.get("--target").getOrDefault {=> options.get("-t").getOrDefault {=> "debug"}}
        let cmd = nonOptions.get(0).getOrDefault {=> "sdk"}
        var cmdNonOptions = if (nonOptions.size > 1) {
            nonOptions[1..]
        } else {
            Array<String>()
        }

        match (cmd) {
            // TODO: Exception
            case cmd => throw Exception("no such command: `${cmd}`")
        }
    }

    private static const BUILD_USAGE = "Usage: cjdev build [OPTIONS] [COMMAND]"
    private static let BUILD_HELP = """
Cangjie's projects build commands

${BUILD_USAGE}

Options:
  -t, --build-type    Target build type, defaults to debug
  -h, --help          Print help

Commands:
  sdk             Build all Cangjie's projects (default)
  compiler, cjc   Build compiler
  runtime,  rt    Build runtime
  std             Build standard library
  stdx            Build standard library extensions
  tools           Build all Cangjie's tools
  <tool_name>     Build one of the tools (values: cjfmt, cjpm, lspserver)
  interop-java    Build Cangjie to Java interop library
  interop-objc    Build Cangjie to Objective-C interop library."""

    private func printHelp() {
        println(BUILD_HELP)
    }
}
