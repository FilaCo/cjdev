package cjdev.utils

public func ifTrue(condition: Bool, f: () -> Unit): Unit {
    if (condition) {
        f()
    }
}

public func ifFalse(condition: Bool, f: () -> Unit): Unit {
    ifTrue(!condition, f)
}
