package cjdev.app

import std.io.{OutputStream, BufferedOutputStream}
import std.env.{getStdOut, getVariable}
import stdx.log.{getGlobalLogger, setGlobalLogger, Logger, LogLevel}
import stdx.logger.SimpleLogger
import cjdev.app.cli.cjDevCmd
import cjdev.third_party.di.{Registry, RegistryBuilder}
import cjdev.domain.git.aggregate_root.Git
import cjdev.domain.init_cmd.aggregate_root.Init

public class CjDev {
    public func run(): Unit {
        initGlobalLogger()
        cjDevCmd(initRegistry()).build()
    }

    private func initGlobalLogger() {
        let bufOutput = BufferedOutputStream<OutputStream>(getStdOut())
        let logger = SimpleLogger(bufOutput)
        logger.level = LogLevel.fromString(getVariable("CJDEV_LOG_LEVEL").getOrDefault {=> "info"})
        setGlobalLogger(logger)
    }

    private func initRegistry() {
        let logger = getGlobalLogger()
        logger.trace("Initializing registry...")
        let registry = Registry.builder().setupDomains().build()
        logger.trace("Registry was successfully initialized!")
        logger.close()
        registry
    }
}

extend RegistryBuilder {
    func setupDomains(): RegistryBuilder {
        addLazy {_ => Git()}.addLazy {_ => Init()}
    }

    // func setupConfig(): RegistryBuilder {
    // }
}

extend LogLevel {
    static func fromEnv(): LogLevel {
        fromString(getVariable("CJDEV_LOG_LEVEL").getOrDefault {=> "info"})
    }

    static func fromString(str: String): LogLevel {
        match (str) {
            case "trace" => LogLevel.TRACE
            case "info" => LogLevel.INFO
            case "warn" => LogLevel.WARN
            case "error" => LogLevel.ERROR
            case _ => throw Exception("not supported")
        }
    }
}
