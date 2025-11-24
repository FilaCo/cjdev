package cjdev.app

import std.io.{OutputStream, BufferedOutputStream}
import std.env.getStdOut
import stdx.log.{getGlobalLogger, setGlobalLogger, Logger, LogLevel}
import stdx.logger.SimpleLogger
import cjdev.app.config.CjDevConfig
import cjdev.app.cli.cjDevCmd

public class CjDev {
    public func run(): Unit {
        initGlobalLogger()
        let cfg = loadConfig()
        // cjDevCmd(cfg).build()
    }

    private func initGlobalLogger() {
        let bufOutput = BufferedOutputStream<OutputStream>(getStdOut())
        let logger = SimpleLogger(bufOutput)
        // TODO: get from env
        logger.level = LogLevel.INFO
        setGlobalLogger(logger)
    }

    private func loadConfig() {
        let logger = getGlobalLogger()
        logger.info("Loading config...")
        logger.info("Config was successfully loaded!")
        logger.close()
    }
}
