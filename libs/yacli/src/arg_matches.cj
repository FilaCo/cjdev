package yacli

public class ArgMatches {
    public func getOne<T>(name: String): ?T where T <: Any {
        None
    }
    public func getMany<T>(name: String): ?Array<T> where ArgT <: Any {
        None
    }
}
