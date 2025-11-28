package yacli

public class ArgMatches {
    public func get_one<ArgT>(name: String): ?ArgT where ArgT <: Any {
        None
    }
    public func get_many<ArgT>(name: String): ?Array<ArgT> where ArgT <: Any {
        None
    }
}
