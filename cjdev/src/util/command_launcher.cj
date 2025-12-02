package cjdev.util

import std.process.{launch, SubProcess}
import yadi.{Registry, RegistryBuilder}
import cjdev.config.GeneralConfig

public interface CommandLauncher {
    func launchCommand(args: Array<String>): SubProcess
}

public class BashCommandLauncher <: CommandLauncher {
    public func launchCommand(args: Array<String>): SubProcess {
        launch("echo bash")
    }
}

public class DockerCommandLauncher <: CommandLauncher {
    public func launchCommand(args: Array<String>): SubProcess {
        launch("echo docker")
    }
}

public func addCommandLauncher(builder: RegistryBuilder): RegistryBuilder {
    builder.addLazy<CommandLauncher> {
        reg: Registry =>
            let generalCfg = reg.get<GeneralConfig>()
            if (generalCfg.useDocker) {
                DockerCommandLauncher()
            } else {
                BashCommandLauncher()
            }
    }
}
