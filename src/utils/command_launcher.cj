package cjdev.utils

import std.collection.Map
import std.fs.Path
import std.process.{launch, ProcessRedirect, SubProcess}

public interface CommandLauncher {
    func launchCommand(cmd: String, args: Array<String>): SubProcess
}

public class BaseCommandLauncher <: CommandLauncher {
    public func launchCommand(cmd: String, args: Array<String>): SubProcess {
        launch(cmd, args)
    }
}

public class DockerCommandLauncher <: CommandLauncher {
    public func launchCommand(cmd: String, args: Array<String>): SubProcess {
        throw Exception()
    }
}
