package cjdev.third_party.cli

public class Argument <: Equatable<Argument> & Hashable {
    private var _description: ?String = None
    private var _kind = Positional
    private var _short: ?Rune = None
    private var _long: ?String = None

    public Argument(private var _name: String) {
    }

    public func withName(name: String): This {
        _name = name

        this
    }

    public func withDescription(description: String): This {
        _description = description

        this
    }

    public func withShort(short: Rune): This {
        _short = short
        _kind = Optional

        this
    }

    public func withLong(long: String): This {
        _long = long
        _kind = Optional

        this
    }

    public func withDefaultValue<T>(defaultValue: T): This {
        this
    }

    public operator func ==(other: Argument) {
        _name == other._name
    }

    public func hashCode(): Int64 {
        _name.hashCode()
    }
}

enum ArgumentKind {
    Positional | Optional
}
