package yadi

import std.sync.ReadWriteLock

protected interface Entry<T> {
    func get(registry: Registry): T
}

protected class Lazy<T> <: Entry<T> {
    private var _instance = None<T>
    private var _locker = ReadWriteLock()

    public Lazy(private let _factory: (Registry) -> T) {}

    public func get(registry: Registry): T {
        _locker.readLock.lock()
        match (_instance) {
            case Some(result) =>
                _locker.readLock.unlock()
                result
            case _ =>
                _locker.readLock.unlock()

                _locker.writeLock.lock()
                // Double check if another thread has initialized the instance
                match (_instance) {
                    case Some(result) =>
                        _locker.writeLock.unlock()
                        result
                    case _ =>
                        let result = _factory(registry)
                        _instance = Some(result)
                        _locker.writeLock.unlock()
                        result
                }
        }
    }
}

protected class Transient<T> <: Entry<T> {
    public Transient(private let _factory: (Registry) -> T) {}

    public func get(registry: Registry): T {
        _factory(registry)
    }
}
