package cjdev.third_party.di

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
        get<T>(Tag())
    }

    public func get<T>(tag: Tag): T {
        (_entries
            .get(tag)
            .getOrThrow {=> Exception("entry has wrong type")} as Entry<T>)
            .getOrThrow {=> Exception("entry not found")}
            .get(this)
    }
}

public class RegistryBuilder {
    private var _entries = HashMap<Tag, Any>()

    public func build(): Registry {
        // TODO: validation
        Registry(this)
    }

    public func addLazy<T>(): This where T <: Injectable<T> {
        addLazy<T>(Tag())
    }

    public func addLazy<T>(tag: Tag): This where T <: Injectable<T> {
        addLazy<T>(tag, T.fromRegistry)
    }

    public func addLazy<T>(factory: (Registry) -> T): This {
        addLazy<T>(Tag(), factory)
    }

    public func addLazy<T>(tag: Tag, factory: (Registry) -> T): This {
        add(tag, Lazy(factory))
    }

    // public func addLazy<InterfaceT, ImplementationT>(): This where ImplementationT <: InterfaceT & Injectable<ImplementationT> {
    //     addLazy<InterfaceT, ImplementationT>(Tag())
    // }
    //
    // public func addLazy<InterfaceT, ImplementationT>(tag: Tag): This where ImplementationT <: InterfaceT & Injectable<ImplementationT> {
    //     addLazy(tag, ImplementationT.fromRegistry)
    // }
    //
    // public func addLazy<InterfaceT, ImplementationT>(factory: (Registry) -> InterfaceT): This where ImplementationT <: InterfaceT {
    //     addLazy(Tag(), factory)
    // }
    //
    // public func addLazy<InterfaceT, ImplementationT>(tag: Tag, factory: (Registry) -> InterfaceT): This where ImplementationT <: InterfaceT {
    //     this
    // }

    public func addTransient<T>(): This where T <: Injectable<T> {
        addTransient<T>(Tag())
    }

    public func addTransient<T>(tag: Tag): This where T <: Injectable<T> {
        addTransient<T>(tag, T.fromRegistry)
    }

    public func addTransient<T>(factory: (Registry) -> T): This {
        addTransient<T>(Tag(), factory)
    }

    public func addTransient<T>(tag: Tag, factory: (Registry) -> T): This {
        add(tag, Transient(factory))
    }

    // public func addTransient<InterfaceT, ImplementationT>(): This where ImplementationT <: InterfaceT & Injectable<ImplementationT> {
    //     addTransient<InterfaceT, ImplementationT>(Tag())
    // }
    //
    // public func addTransient<InterfaceT, ImplementationT>(tag: Tag): This where ImplementationT <: InterfaceT & Injectable<ImplementationT> {
    //     addTransient(tag, ImplementationT.fromRegistry)
    // }
    //
    // public func addTransient<InterfaceT, ImplementationT>(factory: (Registry) -> InterfaceT): This where ImplementationT <: InterfaceT {
    //     addTransient(Tag(), factory)
    // }
    //
    // public func addTransient<InterfaceT, ImplementationT>(tag: Tag, factory: (Registry) -> InterfaceT): This where ImplementationT <: InterfaceT {
    //     this
    // }

    public func add<T>(tag: Tag, entry: Entry<T>): This {
        _entries.add(tag, entry as Any)

        this
    }

    protected func getEntries(): ReadOnlyMap<Tag, Any> {
        _entries
    }
}
