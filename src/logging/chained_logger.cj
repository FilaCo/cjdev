package cjdev.logging

import stdx.log.Logger

protected class ChainedLogger {
    protected ChainedLogger() {}
    static func builder<LoggerT>(start: LoggerT): ChainedLoggerBuilder where LoggerT <: Logger {
        ChainedLoggerBuilder()
    }

    static func builder<LoggerT>(factory: () -> LoggerT): ChainedLoggerBuilder where LoggerT <: Logger {
        builder(factory())
    }
}

protected class ChainedLoggerBuilder {
    protected ChainedLoggerBuilder() {
    }
}
