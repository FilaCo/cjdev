package cjdev.util

import std.process.SubProcess

public interface CommandExecutor {
    func execute(rawCmd: String): SubProcess
}
