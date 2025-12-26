package cjdev.features

import std.collection.{Map, ReadOnlyMap}
import std.env.{exit, getWorkingDirectory}
import std.fs.Path
import std.process.{launch, ProcessRedirect, SubProcess}
import stdx.log.Logger

public class Dc {
    public Dc(private let logger_: Logger, private let launcher: CommandLauncher) {}

    public func execute<OptionsMapT>(options: OptionsMapT, nonOptions: Array<String>): Unit where OptionsMapT <: ReadOnlyMap<String,
    String> {
        if (options.contains("help") || options.contains("h")) {
            printHelp()
            return
        }
        let cmd = nonOptions.get(0).getOrDefault {=> "bash"}
        let args = if (nonOptions.size > 1) {
            nonOptions[1..]
        } else {
            Array<String>()
        }

        exit(launcher.launchCommand(cmd, args).wait())
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

public struct ContainerSettings {
    public ContainerSettings(public let hostWorkdir!: Path, public let containerWorkdir!: Path,
        public let containerName!: String) {}
}

public open class CommandLauncher {
    public func launchCommand(cmd: String, args: Array<String>, workDir!: ?Path = None,
        envVars!: ?Map<String, String> = None, stdIn!: ProcessRedirect = Inherit, stdOut!: ProcessRedirect = Inherit,
        stdErr!: ProcessRedirect = Inherit): SubProcess {
        launchCommandImpl(cmd, args, workDir: workDir, envVars: envVars, stdIn: stdIn, stdOut: stdOut, stdErr: stdErr)
    }

    protected open func launchCommandImpl(cmd: String, args: Array<String>, workDir!: ?Path,
        envVars!: ?Map<String, String>, stdIn!: ProcessRedirect, stdOut!: ProcessRedirect, stdErr!: ProcessRedirect): SubProcess {
        launch(cmd, args, workingDirectory: workDir, environment: envVars, stdIn: stdIn, stdOut: stdOut, stdErr: stdErr)
    }
}

public class ContainerCommandLauncher <: CommandLauncher {
    public ContainerCommandLauncher(private let logger_: Logger, private let settings_: ContainerSettings) {}

    protected func launchCommandImpl(cmd: String, args: Array<String>, workDir!: ?Path, envVars!: ?Map<String, String>,
        stdIn!: ProcessRedirect, stdOut!: ProcessRedirect, stdErr!: ProcessRedirect): SubProcess {
        let innerCmd = [cmd].concat(args)
        super.launchCommandImpl("docker",
            ["container", "run", "-it", "--rm", "-v", getDockerVolumeArg(), "-w", getContainerPwd(workDir).toString(),
                settings_.containerName, "bash", "-lc"].concat(innerCmd), workDir: workDir, envVars: envVars,
            stdIn: stdIn, stdOut: stdOut, stdErr: stdErr)
    }

    private func getDockerVolumeArg() {
        "${settings_.hostWorkdir}:${settings_.containerWorkdir}:rw"
    }

    private func getContainerPwd(hostPwd: ?Path): Path {
        let relativePath = hostPwd
            .getOrDefault {=> getWorkingDirectory()}
            .normalize()
            .toString()
            .split(Path.Separator, removeEmpty: true)
            .removePrefix(settings_.hostWorkdir.toString().split(Path.Separator, removeEmpty: true)) |> {
            rawSegments: Array<String> => String.join(rawSegments, delimiter: Path.Separator)
        } |> {rawRelativePath: String => Path(rawRelativePath)}
        if (relativePath.isEmpty()) {
            return settings_.containerWorkdir
        }

        println(relativePath)

        settings_.containerWorkdir.join(relativePath)
    }
}
