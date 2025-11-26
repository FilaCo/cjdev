package cjdev

import std.io.{OutputStream, BufferedOutputStream}
import std.env.{getStdOut, getVariable}
import std.fs.{exists, Path}
import stdx.log.{getGlobalLogger, setGlobalLogger, Logger, LogLevel}
import stdx.logger.SimpleLogger
import stdx.serialization.serialization.DataModel
import yadi.{Registry, RegistryBuilder}
import cjdev.cli.{addCjDevCmd, CJDEV_CMD_LABEL, addDcCmd}
import cjdev.config.{CjDevConfig}
import cli.Command
import cangjie_toml.cangjie_toml.FromToml

public class CjDev {
    public func run(): Unit {
        let reg = initRegistry()
        reg.get<Command>(CJDEV_CMD_LABEL).build()
    }

    private func initGlobalLogger() {
        let bufOutput = BufferedOutputStream<OutputStream>(getStdOut())
        let logger = SimpleLogger(bufOutput)
        logger.level = LogLevel.fromEnv()
        setGlobalLogger(logger)
    }

    private func initRegistry() {
        Registry.builder() |> addLogger |> addCmds |> addConfigIfExists |> {builder: RegistryBuilder => builder.build()}
    }

    private func addLogger(builder: RegistryBuilder): RegistryBuilder {
        builder.addLazy<Logger>("cjdev.logger.simple") {
            _ =>
                let bufOutput = BufferedOutputStream<OutputStream>(getStdOut())
                let logger = SimpleLogger(bufOutput)
                logger.level = LogLevel.fromEnv()
                logger
        }
    }

    private func addCmds(builder: RegistryBuilder): RegistryBuilder {
        builder |> addCjDevCmd |> addDcCmd
    }

    private func addConfigIfExists(builder: RegistryBuilder): RegistryBuilder {
        const CJDEV_CONFIG_PATH = "cjdev.toml"
        if (!exists(CJDEV_CONFIG_PATH)) {
            return builder
        }

        builder.addLazy<CjDevConfig>("cjdev.config.cjdev") {
            _ => DataModel.fromTomlFile(CJDEV_CONFIG_PATH) |> CjDevConfig.deserialize
        }
    }
}

extend LogLevel {
    static func fromEnv(): LogLevel {
        fromString(getVariable("CJDEV_LOG_LEVEL").getOrDefault {=> "INFO"})
    }

    // @throws UnsupportedLogLevelException
    static func fromString(str: String): LogLevel {
        match (str) {
            case "OFF" => LogLevel.OFF
            case "FATAL" => LogLevel.FATAL
            case "ERROR" => LogLevel.ERROR
            case "WARN" => LogLevel.WARN
            case "INFO" => LogLevel.INFO
            case "DEBUG" => LogLevel.DEBUG
            case "TRACE" => LogLevel.TRACE
            case "ALL" => LogLevel.ALL
            case _ => throw UnsupportedLogLevelException(str)
        }
    }
}

public class UnsupportedLogLevelException <: Exception {
    public UnsupportedLogLevelException(name: String) {
        super("LogLevel: ${name} is not supported")
    }
}
