package yacli

import std.collection.HashMap
import std.env.getCommandLine

public class Command <: Equatable<Command> & Hashable {
    private var _version = None<String>
    private var _about = None<String>
    private var _usage = None<String>
    private var _args = HashMap<String, Arg>()
    private var _subcommands = HashMap<String, Command>()

    public Command(private var _name: String) {
    }

    public func name(name: String): This {
        _name = name

        this
    }

    public func version(version: String): This {
        _version = version

        this
    }

    public func about(about: String): This {
        _about = about

        this
    }

    public func arg(arg: Arg): This {
        _args.add(arg.getName(), arg)

        this
    }

    public func arg(factory: () -> Arg): This {
        arg(factory())
    }

    public func subcommand(command: Command): This {
        _subcommands.add(command.getName(), command)

        this
    }

    public func subcommand(factory: () -> Command): This {
        subcommand(factory())
    }

    public func getMatches(): ArgMatches {
        getMatches(getCommandLine())
    }

    public func getMatches<ArgsT, ArgT>(rawArgs: ArgsT): ArgMatches where ArgsT <: Iterable<ArgT>,
        ArgT <: Any & ToString {
        ArgMatches()
    }

    public func getName(): String {
        _name
    }

    public operator func ==(other: Command) {
        _name == other._name
    }

    public func hashCode(): Int64 {
        _name.hashCode()
    }
}
