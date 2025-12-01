package yacli

public class Arg {
    private var _help = None<String>
    private var _action = Set
    private var _short = None<Rune>
    private var _long = None<String>
    private var _valueName: String

    public Arg(private var _name: String) {
        _valueName = _name.toAsciiUpper()
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

        this
    }

    public func long(long: String): This {
        _long = long

        this
    }

    public func defaultValue<T>(defaultValue: T): This {
        this
    }

    public func valueName(valueName: String): This {
        _valueName = valueName

        this
    }

    public func getName(): String {
        _name
    }

    public func getHelp(): ?String {
        _help
    }

    public func getAction(): ArgAction {
        _action
    }

    public func getShort(): ?Rune {
        _short
    }

    public func getLong(): ?String {
        _long
    }

    public func getValueName(): String {
        _valueName
    }
}

public enum ArgAction {
    Set | Append | SetTrue | SetFalse | Count | Help | Version
}
