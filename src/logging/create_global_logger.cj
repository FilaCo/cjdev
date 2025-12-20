package cjdev.logging

import std.env.{getVariable}
import std.fs.{Path, exists}
import std.io.{BufferedOutputStream, OutputStream}
import stdx.log.{Logger, LogLevel}
import stdx.logger.SimpleLogger

public func createGlobalLogger(): Logger {
    let logLevel = LogLevel.fromEnv()
    ChainedLogger.builder {
        =>
            let bufOutput = BufferedOutputStream<OutputStream>(getStdOut())
            let logger = PrettyLogger(bufOutput)
            logger.level = logLevel
            logger
    }.next {
        =>
            let logDir = Path(CJDEV_LOG_DIR)

            if (!exists(logDir)) {
            }
    }
}

extend LogLevel {
    static func fromEnv(): LogLevel {
        fromString(CJDEV_LOG_LEVEL)
    }

    /**
     * @throws UnsupportedLogLevelException
     */
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

protected class UnsupportedLogLevelException <: Exception {
    UnsupportedLogLevelException(name: String) {
        super("LogLevel: ${name} is not supported")
    }
}
