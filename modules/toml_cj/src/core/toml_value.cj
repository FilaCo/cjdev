package toml_cj.core

public enum TOMLValue {
    TOMLString(String)
    | TOMLBoolean(Bool)
    | TOMLArray(Array<TOMLValue>)
    // | TOMLInlineTable(Array<TOMLKeyValData>)
    // | TOMLDateTime(TOMLDateTimeData)
    | TOMLFloat(Float64)
    | TOMLInteger(Int64)
}
