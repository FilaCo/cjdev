package cjdev.util.cli

import std.collection.HashSet

public class Command <: Equatable<Command> & Hashable {
    private var _version: ?String = None
    private var _description: ?String = None
    private var _usage: ?String = None
    private var _aliases = HashSet<String>()
    private var _arguments = HashSet<Argument>()
    private var _subcommands = HashSet<Command>()

    public Command(private var _name: String) {
    }

    public func withName(name: String): This {
        _name = name

        this
    }

    public func withVersion(version: String): This {
        _version = version

        this
    }

    public func withDescription(description: String): This {
        _description = description

        this
    }

    public func withUsage(usage: String): This {
        _usage = usage

        this
    }

    public func withAlias(alias: String): This {
        _aliases.add(alias)

        this
    }

    public func withArgument(argument: Argument): This {
        _arguments.add(argument)

        this
    }

    public func withArgument(factory: () -> Argument): This {
        withArgument(factory())
    }

    public func withSubcommand(command: Command): This {
        _subcommands.add(command)

        this
    }

    public func withSubcommand(factory: () -> Command): This {
        withSubcommand(factory())
    }

    public func getMatches(): Int64 {
        0
    }

    public operator func ==(other: Command) {
        _name == other._name
    }

    public func hashCode(): Int64 {
        _name.hashCode()
    }
}
