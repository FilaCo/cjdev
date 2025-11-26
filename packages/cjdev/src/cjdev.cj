package cjdev

import std.io.{OutputStream, BufferedOutputStream}
import std.env.{getStdOut, getVariable}
import stdx.log.{getGlobalLogger, setGlobalLogger, Logger, LogLevel}
import stdx.logger.SimpleLogger
import yadi.Registry
import cjdev.command.{addCjDevCmd, CJDEV_CMD_LABEL}
import cli.Command

public class CjDev {
    public func run(): Unit {
        initGlobalLogger()
        let registry = initRegistry()
        registry.get<Command>(CJDEV_CMD_LABEL).build()
    }

    private func initGlobalLogger() {
        let bufOutput = BufferedOutputStream<OutputStream>(getStdOut())
        let logger = SimpleLogger(bufOutput)
        logger.level = LogLevel.fromEnv()
        setGlobalLogger(logger)
    }

    private func initRegistry() {
        let logger = getGlobalLogger()
        logger.trace("Initializing registry...")
        let registryBuilder = Registry.builder()
        addCjDevCmd(registryBuilder)
        logger.trace("Registry was successfully initialized!")
        logger.close()
        registryBuilder.build()
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
