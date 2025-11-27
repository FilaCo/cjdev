package cjdev

import std.io.{OutputStream, BufferedOutputStream}
import std.env.{getStdOut, getVariable}
import stdx.log.{getGlobalLogger, setGlobalLogger, Logger, LogLevel}
import stdx.logger.SimpleLogger
import stdx.serialization.serialization.DataModel
import yadi.{Registry, RegistryBuilder}
import cjdev.cli.{addCommand, CJDEV_CMD_LABEL}
import cjdev.config.addConfig
import cjdev.util.addCommandLauncher
import cli.Command

public class CjDev {
    public func run(): Unit {
        let reg = initRegistry()
        reg.get<Command>(CJDEV_CMD_LABEL).build()
    }

    private func initRegistry() {
        Registry.builder() |> addLogger |> addCommand |> addConfig |> addUtils |> {
            builder: RegistryBuilder => builder.build()
        }
    }

    private func addLogger(builder: RegistryBuilder): RegistryBuilder {
        builder.addLazy<Logger>("cjdev.logger.global") {
            _ =>
                let bufOutput = BufferedOutputStream<OutputStream>(getStdOut())
                let logger = SimpleLogger(bufOutput)
                logger.level = LogLevel.fromEnv()
                logger
        }
    }

    private func addUtils(builder: RegistryBuilder): RegistryBuilder {
        builder |> addCommandLauncher
    }
}

extend LogLevel {
    static func fromEnv(): LogLevel {
        fromString(getVariable("CJDEV_LOG_LEVEL").getOrDefault {=> "INFO"})
    }

    // @throws UnsupportedLogLevelException
    static func fromString(str: String): LogLevel {
        match (str.toAsciiUpper()) {
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
