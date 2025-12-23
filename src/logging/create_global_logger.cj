package cjdev.logging

import std.env.getStdErr
import std.fs.{Directory, File, OpenMode, Path, exists}
import std.io.{BufferedOutputStream, OutputStream}
import stdx.log.{Logger, LogLevel}
import stdx.logger.TextLogger

public func createGlobalLogger(logDir: Path): Logger {
    SeqLogger.builder {
        =>
            let logger = PrettyLogger(getStdErr())
            logger.level = LogLevel.ERROR
            logger
    }.next {
        =>
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
            logger
    }.build()
}
