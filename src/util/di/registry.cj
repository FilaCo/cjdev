package cjdev.util.di

import std.collections.HashMap

public class Registry {
    Registry(private let inner: HashMap<Tag, Entry>) {
    }

    public static func builder(): RegistryBuilder {
        RegistryBuilder()
    }

    public func resolve<T>(): T {
        throw Exception("not implemented")
    }

    public func resolve<T>(tag: Tag): T {
        throw Exception("not implemented")
    }
}

public enum RegistryError {}

public class RegistryBuilder {
    public RegistryBuilder() {}
    
    public func build(): Result<Registry, RegistryError> {
      Ok(Registry())
  }
}
