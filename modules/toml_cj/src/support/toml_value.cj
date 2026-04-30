protected package toml_cj.support

import std.ast.*
import std.collection.*

public enum TOMLValue <: ToString & ToTokens {
    | TOMLString(TOMLStringData)
    | TOMLBoolean(Bool)
    | TOMLArray(Array<TOMLValue>)
    | TOMLInlineTable(Array<TOMLKeyValueData>)
    // | TOMLDatetime(TOMLDateTimeData)
    | TOMLFloat(Float64)
    | TOMLInteger(Int64)
    | TOMLInterpolated(Tokens)

    public func toString(): String {
        match (this) {
            case TOMLString(sd) => sd.toString()
            case TOMLBoolean(b) => b.toString()
            case TOMLArray(arr) => arr.toString()
            case TOMLInlineTable(it) => "{ ${it |> collectString(delimiter: ", ")} }"
            // case TOMLDatetime(dt) => "\"${s}\""
            case TOMLFloat(f) => f.toString()
            case TOMLInteger(i) => i.toString()
            case TOMLInterpolated(t) => t.toString()
        }
    }

    public func toTokens(): Tokens {
        match (this) {
            case TOMLString(sd) => quote(TOMLString($sd))
            case TOMLBoolean(b) => quote(TOMLBoolean($b))
            case TOMLArray(arr) =>
                let arrTokens = joinTokens(arr, open: quote([), close: quote(]), sep: quote(,))
                quote(TOMLArray($arr))
            case TOMLInlineTable(it) =>
                let itTokens = joinTokens(it, open: quote({), close: quote(}), sep: quote(,))
                quote(TOMLInlineTable($itTokens))
            // case TOMLDatetime(dt) => "\"${s}\""
            case TOMLFloat(f) => quote(TOMLFloat($f))
            case TOMLInteger(i) => quote(TOMLInteger($i))
            case TOMLInterpolated(t) => quote(toTOMLValue($t))
        }
    }
}

sealed abstract class TOMLStringData <: ToString & ToTokens {}

public class TOMLMultilineBasicString <: TOMLStringData {
    public TOMLMultilineBasicString(private let inner: String) {}

    public func toString(): String {
        "\"\"\"${inner}\"\"\""
    }

    public func toTokens(): Tokens {
        quote(TOMLMultilineBasicString($inner))
    }
}

public class TOMLBasicString <: TOMLStringData {
    public TOMLBasicString(private let inner: String) {}

    public func toString(): String {
        "\"${inner}\""
    }

    public func toTokens(): Tokens {
        quote(TOMLBasicString($inner))
    }
}

public class TOMLMultilineLiteralString <: TOMLStringData {
    public TOMLMultilineLiteralString(private let inner: String) {}

    public func toString(): String {
        "'''${inner}'''"
    }

    public func toTokens(): Tokens {
        quote(TOMLMultilineLiteralString($inner))
    }
}

public class TOMLLiteralString <: TOMLStringData {
    public TOMLLiteralString(private let inner: String) {}

    public func toString(): String {
        "'${inner}'"
    }

    public func toTokens(): Tokens {
        quote(TOMLLiteralString($inner))
    }
}

sealed abstract class TOMLKey <: ToString & ToTokens {}

public abstract class TOMLSimpleKey <: TOMLKey {}

public class TOMLUnquotedKey <: TOMLSimpleKey {
    public TOMLUnquotedKey(private let inner: String) {}

    public func toString(): String {
        inner
    }

    public func toTokens(): Tokens {
        quote(TOMLUnquotedKey($inner))
    }
}

public class TOMLQuotedKey <: TOMLSimpleKey {
    private let inner: TOMLStringData

    public init(bs: TOMLBasicString) {
        inner = bs
    }

    public init(ls: TOMLLiteralString) {
        inner = ls
    }

    public func toString(): String {
        inner.toString()
    }

    public func toTokens(): Tokens {
        quote(TOMLQuotedKey($inner))
    }
}

public class TOMLDottedKey <: TOMLKey {
    public TOMLDottedKey(private let parts: Array<TOMLSimpleKey>) {}

    public func toString(): String {
        parts |> collectString(delimiter: '.')
    }

    public func toTokens(): Tokens {
        let partsTokens = joinTokens(parts, open: quote([), close: quote(]), sep: quote(,))
        quote(TOMLDottedKey($parts))
    }
}

public struct TOMLKeyValueData <: ToString & ToTokens {
    public TOMLKeyValueData(public let key!: TOMLKey, public let value!: TOMLValue) {}

    public func toString(): String {
        "${key} = ${value}"
    }

    public func toTokens(): Tokens {
        quote(TOMLKeyValue(key: $key, value: $value))
    }
}
