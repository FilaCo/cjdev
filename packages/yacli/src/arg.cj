package yacli

public class Arg <: Equatable<Arg> & Hashable {
    private var _help = None<String>
    private var _kind = Pos
    private var _action = Set
    private var _short = None<Rune>
    private var _long = None<String>
    private var _valueName = None<String>

    public Arg(private var _name: String) {
    }

    public func name(name: String): This {
        _name = name

        this
    }

    public func help(help: String): This {
        _help = help

        this
    }

    public func action(action: ArgAction): This {
        _action = action

        this
    }

    public func short(short: Rune): This {
        _short = short
        _kind = Opt

        this
    }

    public func long(long: String): This {
        _long = long
        _kind = Opt

        this
    }

    public func defaultValue<T>(value: T): This {
        this
    }

    public func getName(): String {
        _name
    }

    public operator func ==(other: Arg) {
        _name == other._name
    }

    public func hashCode(): Int64 {
        _name.hashCode()
    }
}

enum ArgKind {
    Pos | Opt
}

public enum ArgAction {
    Set | Append | SetTrue | SetFalse | Count | Help | Version
}
