package cjdev.logging

import std.io.{OutputStream, StringWriter}
import stdx.log.{Attr, Logger, LogLevel, LogRecord}

public class PrettyLogger<O> <: Logger where O <: OutputStream {
    private var level_ = LogLevel.INFO
    private let writer_: StringWriter<O>
    public mut prop level: LogLevel {
        get() {
            level_
        }
        set(v) {
            level_ = v
        }
    }

    public PrettyLogger(output: O) {
        writer_ = StringWriter(output)
    }

    public func log(record: LogRecord): Unit {
        writer_.writeln("${record.level}: ${record.message}")
        writer_.flush()
    }

    public func isClosed(): Bool {
        ((writer_ as Resource)?.isClosed()).getOrDefault {=> false}
    }

    public func close(): Unit {
        (writer_ as Resource)?.close()
    }

    public func withAttrs(_: Array<Attr>): Logger {
        this
    }
}
