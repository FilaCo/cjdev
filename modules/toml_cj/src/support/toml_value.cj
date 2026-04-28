protected package toml_cj.support

import std.ast.*

public enum TOMLValue <: ToString & ToTokens {
    TOMLString(String)
    | TOMLBoolean(Bool)
    | TOMLArray(Array<TOMLValue>)
    // | TOMLInlineTable(Array<TOMLKeyValData>)
    // | TOMLDateTime(TOMLDateTimeData)
    | TOMLFloat(Float64)
    | TOMLInteger(Int64)

    public func toString(): String {
        throw Exception()
    }

    public func toTokens(): Tokens {
        throw Exception()
    }
}
