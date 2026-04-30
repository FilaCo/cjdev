protected package toml_cj.support

import std.ast.*
import std.collection.*

public struct TOMLFile <: ToString & ToTokens {
    public TOMLFile(public let exprs: Array<TOMLExpr>) {}

    public func toString(): String {
        exprs |> collectString(delimiter: NL)
    }

    public func toTokens(): Tokens {
        let toks = Tokens()

        for (expr in exprs) {
            toks.append(expr.toTokens())
        }

        toks
    }
}

public enum TOMLExpr <: ToString & ToTokens {
    | TOMLKeyValue(TOMLKeyValueData)
    | TOMLStdTable(TOMLKey)
    | TOMLArrayTable(TOMLKey)

    public func toString(): String {
        match (this) {
            case TOMLKeyValue(kv) => kv.toString()
            case TOMLStdTable(k) => "[${k}]"
            case TOMLArrayTable(k) => "[[${k}]]"
        }
    }

    public func toTokens(): Tokens {
        match (this) {
            case TOMLKeyValue(kv) => quote(TOMLKeyValue($kv))
            case TOMLStdTable(k) => quote(TOMLStdTable($k))
            case TOMLArrayTable(k) => quote(TOMLArrayTable($k))
        }
    }
}
