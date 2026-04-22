package toml_cj.core

import std.deriving.*

@Derive[Equatable]
public class TOMLFile {
    public TOMLFile(public let exprs: Array<TOMLExpr>) {}
}

@Derive[Equatable]
public enum TOMLExpr {
    TOMLKeyVal(TOMLKeyValData)
    | TOMLStdTable(String)
    | TOMLArrayTable(String)
}

@Derive[Equatable]
public class TOMLKeyValData {
    public TOMLKeyValData(public let key: String, public let val: TOMLVal) {}
}

@Derive[Equatable]
public enum TOMLVal {
    TOMLString(String)
    | TOMLBoolean(Bool)
    | TOMLArray(Array<TOMLVal>)
    | TOMLInlineTable(Array<TOMLKeyValData>)
    // | TOMLDateTime(TOMLDateTimeData)
    | TOMLFloat(Float64)
    | TOMLInteger(Int64)
}
