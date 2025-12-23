package cjdev.utils

import std.fs.Path
import std.process.{launch, ProcessRedirect, SubProcess}

public interface CommandLauncher {
    func launchCommand(cmd: String, args: Array<String>, workDir!: ?Path = None, envVars!: ?Map<String, String> = None,
        stdIn!: ProcessRedirect = Inherit, stdOut!: ProcessRedirect = Inherit, stdErr!: ProcessRedirect = Inherit,
        timeout!: ?Duration = None): SubProcess
}

public class BashCommandLauncher <: CommandLauncher {
    public func launchCommand(cmd: String, args: Array<String>, workDir!: ?Path = None,
        envVars!: ?Map<String, String> = None, stdIn!: ProcessRedirect = Inherit, stdOut!: ProcessRedirect = Inherit,
        stdErr!: ProcessRedirect = Inherit, timeout!: ?Duration = None): SubProcess {
        launch("bash -c", [cmd, ..args], workDir: workDir, envVars: envVars, stdIn: stdIn, stdOut: stdOut, stdErr: stdErr, timeout: timeout)
    }
}

public class DockerCommandLauncher <: CommandLauncher {
    public func launchCommand(cmd: String, args: Array<String>, workDir!: ?Path = None,
        envVars!: ?Map<String, String> = None, stdIn!: ProcessRedirect = Inherit, stdOut!: ProcessRedirect = Inherit,
        stdErr!: ProcessRedirect = Inherit, timeout!: ?Duration = None): SubProcess {
        throw Exception()
    }
}
