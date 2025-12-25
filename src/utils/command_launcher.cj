package cjdev.utils

import std.collection.Map
import std.fs.Path
import std.process.{launch, ProcessRedirect, SubProcess}

public interface CommandLauncher {
    func launchCommand(cmd: String, args: Array<String>): SubProcess
}

public open class BaseCommandLauncher <: CommandLauncher {
    public func launchCommand(cmd: String, args: Array<String>): SubProcess {
        launch(cmd, args)
    }
}

public class CjDevContainerCommandLauncher <: BaseCommandLauncher {
    public func launchCommand(cmd: String, args: Array<String>): SubProcess {
        super.launch("docker", ["container", "run", "-it", "--rm", "-v", cmd].concat(args))
    }
}
