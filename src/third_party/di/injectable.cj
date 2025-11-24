package cjdev.third_party.di

public interface Injectable<T> {
    static func fromRegistry(registry: Registry): T
}
