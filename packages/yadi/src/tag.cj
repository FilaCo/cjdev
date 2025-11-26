package yadi

import std.deriving.Derive
import std.reflect.TypeInfo

@Derive[Equatable, Hashable, ToString]
protected struct Tag {
    Tag(protected let inner: String) {}
    static func of<T>(): Tag {
        Tag(TypeInfo.of<T>().qualifiedName)
    }
}
