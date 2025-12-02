package yadi

import std.deriving.Derive
import std.reflect.TypeInfo

@Derive[Equatable, Hashable]
protected struct Tag <: ToString {
    Tag(protected let inner: String) {}

    static func of<T>(): Tag {
        Tag(TypeInfo.of<T>().qualifiedName)
    }

    public func toString(): String {
        inner
    }
}
