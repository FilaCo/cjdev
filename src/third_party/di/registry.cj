package cjdev.third_party.di

import std.reflect.TypeInfo
import std.collection.{HashMap, ReadOnlyMap}

public class Registry {
    private let _entries: ReadOnlyMap<String, Any>

    public static func builder(): RegistryBuilder {
        RegistryBuilder()
    }

    protected Registry(builder: RegistryBuilder) {
        _entries = builder.getEntries()
    }

    public func get<T>(): T {
        (_entries
            .get(tag<T>())
            .getOrThrow {=> Exception("entry not found")} as Entry<T>)
            .getOrThrow {=> Exception("entry has wrong type")}
            .get(this)
    }
}

public class RegistryBuilder {
    private var _entries = HashMap<String, Any>()

    public func build(): Registry {
        // TODO: validation
        Registry(this)
    }

    public func addLazy<T>(factory: (Registry) -> T): This {
        add(Lazy(factory))
    }

    public func addTransient<T>(factory: (Registry) -> T): This {
        add(Transient(factory))
    }

    public func add<T>(entry: Entry<T>): This {
        _entries.add(tag<T>(), entry)

        this
    }

    protected func getEntries(): ReadOnlyMap<String, Any> {
        _entries
    }
}

private func tag<T>(): String {
    TypeInfo.of<T>().qualifiedName
}
