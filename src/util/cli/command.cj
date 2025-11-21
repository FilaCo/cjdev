package cjdev.util.cli

public class Command {
    private var name: ?String = None
    private var version: ?String = None

    public Command(name: String) {
        this.withName(name)
    }

    private init() {}

    public func withName(name: String): This {
        this.name = name

        this
    }

    public func withVersion(version: String): This {
        this.version = Some(version)

        this
    }

    public func withArgument(argument: Argument): This {
        this
    }

    public func withArgument(director: (Argument) -> Argument): This {
        withArgument(director(Argument()))
    }

    public func withSubCommand(command: Command): This {
        this
    }

    public func withSubCommand(director: (Command) -> Command): This {
        withSubCommand(director(Command()))
    }
}
