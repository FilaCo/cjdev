package cjdev.logging

import std.collection.ArrayList
import stdx.log.{Attr, Logger, LogLevel, LogRecord}
import cjdev.utils.{ifFalse, ifTrue}

public class SeqLogger <: Logger {
    private let loggers_: ArrayList<Logger>

    public mut prop level: LogLevel {
        get() {
            loggers_.iterator().map {logger => logger.level}.min().getOrDefault {=> LogLevel.OFF}
        }
        set(v) {
            loggers_.iterator().forEach {logger => logger.level = v}
        }
    }

    public SeqLogger(builder: SeqLoggerBuilder) {
        loggers_ = builder.loggers
    }

    public func log(record: LogRecord): Unit {
        loggers_.iterator().forEach {logger => ifTrue(record.level >= logger.level) {=> logger.log(record)}}
    }

    public func isClosed(): Bool {
        loggers_
            .iterator()
            .map {logger => logger.isClosed()}
            .reduce {acc, curIsClosed => acc && curIsClosed}
            .getOrDefault {=> true}
    }

    public func close(): Unit {
        loggers_.iterator().forEach {
            logger => ifFalse(logger.isClosed()) {
                => logger.close()
            }
        }
    }

    public func withAttrs(_: Array<Attr>): Logger {
        this
    }

    public static func builder(): SeqLoggerBuilder {
        SeqLoggerBuilder()
    }

    public static func builder(first: Logger): SeqLoggerBuilder {
        SeqLoggerBuilder(first)
    }

    public static func builder(factory: () -> Logger): SeqLoggerBuilder {
        SeqLoggerBuilder(factory())
    }
}

public class SeqLoggerBuilder {
    private var loggers_ = ArrayList<Logger>(3)

    protected prop loggers: ArrayList<Logger> {
        get() {
            loggers_
        }
    }

    protected SeqLoggerBuilder() {
    }

    protected init(first: Logger) {
        loggers_.add(first)
    }

    public func next(logger: Logger): This {
        loggers_.add(logger)

        this
    }

    public func next(factory: () -> Logger): This {
        next(factory())
    }

    public func build(): SeqLogger {
        SeqLogger(this)
    }
}
