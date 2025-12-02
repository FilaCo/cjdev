package yadi

import std.reflect.TypeInfo
import std.collection.{HashMap, ReadOnlyMap}

public class Registry {
    private let _entries: ReadOnlyMap<Tag, Any>

    public static func builder(): RegistryBuilder {
        RegistryBuilder()
    }

    protected Registry(builder: RegistryBuilder) {
        _entries = builder.getEntries()
    }

    public func get<T>(): T {
        let tag = Tag.of<T>()
        get<T>(tag)
    }

    public func get<T>(label: String): T {
        let tag = Tag(label)
        get<T>(tag)
    }

    private func get<T>(tag: Tag): T {
        if (let Some(item) <- _entries.get(tag)) {
            if (let Some(entry) <- (item as Entry<T>)) {
                return entry.get(this)
            }
            throw RegistryEntryHasWrongTypeException(tag, TypeInfo.of<T>(), TypeInfo.of(item))
        }
        throw RegistryEntryNotFoundException(tag)
    }
}

public class RegistryBuilder {
    private var _entries = HashMap<Tag, Any>()

    public func build(): Registry {
        // TODO: validation
        Registry(this)
    }

    public func addLazy<T>(factory: (Registry) -> T): This {
        add(Lazy(factory))
    }

    public func addLazy<T>(label: String, factory: (Registry) -> T): This {
        add(Tag(label), Lazy(factory))
    }

    public func addTransient<T>(factory: (Registry) -> T): This {
        add(Transient(factory))
    }

    public func addTransient<T>(label: String, factory: (Registry) -> T): This {
        add(Tag(label), Transient(factory))
    }

    protected func getEntries() {
        _entries
    }

    private func add<InterfaceT, EntryT>(entry: EntryT): This where EntryT <: Entry<InterfaceT> {
        add(Tag.of<InterfaceT>(), entry)
    }

    private func add<InterfaceT, EntryT>(tag: Tag, entry: EntryT): This where EntryT <: Entry<InterfaceT> {
        _entries.add(tag, entry)

        this
    }
}

public class RegistryEntryNotFoundException <: Exception {
    RegistryEntryNotFoundException(tag: Tag) {
        super("entry for tag `${tag}` not found")
    }

    protected func getClassName() {
        "RegistryEntryNotFoundException"
    }
}

public class RegistryEntryHasWrongTypeException <: Exception {
    RegistryEntryHasWrongTypeException(tag: Tag, expected: TypeInfo, actual: TypeInfo) {
        super("entry for tag `${tag}` has wrong type. Expected type: ${expected}, actual: ${actual}")
    }
    protected func getClassName() {
        "RegistryEntryHasWrongTypeException"
    }
}
