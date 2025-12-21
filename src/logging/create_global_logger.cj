package cjdev.logging

import std.env.getStdOut
import std.fs.{Directory, File, OpenMode, Path, exists}
import std.io.{BufferedOutputStream, OutputStream}
import stdx.log.{Logger, LogLevel}
import stdx.logger.TextLogger
import cjdev.env.{CJDEV_LOG_LEVEL, CJDEV_LOG_DIR}

public func createGlobalLogger(): Logger {
    let logLevel = LogLevel.fromEnv()
    SeqLogger.builder {
        =>
            let logger = PrettyLogger(getStdOut())
            logger.level = logLevel
            logger
    }.next {
        =>
            let logDir = Path(CJDEV_LOG_DIR)
            if (!exists(logDir)) {
                Directory.create(logDir)
            }
            let logFilePath = logDir.join("cjdev.log")
            let logFile = if (exists(logFilePath)) {
                File(logFilePath, Append)
            } else {
                File.create(logFilePath)
            }
            let bufOutput = BufferedOutputStream<OutputStream>(logFile)
            let logger = TextLogger(bufOutput)
            logger.level = logLevel
            logger
    }.build()
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
