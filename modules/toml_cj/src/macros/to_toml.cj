macro package toml_cj.macros

import std.ast.*
import dslkit.macros.*
public import toml_cj.support.*

/**
 * [TOML v1.1.0 grammar](https://github.com/toml-lang/toml/blob/1.1.0/toml.abnf)
 */
@GrammarMacro[
    Main := TValue
    // Overall Structure
    TValue -> TOMLValue := TBoolean
    // File := (exprs: Expr[cangjie.NL...]+) cangjie.EOF { TOMLFile(exprs) }

    // Expr := (kv: KeyVal) Comment? { TOMLKeyVal(kv) }
    //       | (t: Table) Comment? { t }

    // // Comment
    // Comment := "#" ~! cangjie.NL { () }

    // // Key-Value pairs
    // KeyVal := (k: Key) "=" (v: Val) { TOMLKeyValData(k, v) }
    // Key    := SimpleKey
    //         | DottedKey

    // Val -> TOMLVal := TString
    //                 | Boolean
    //                 | TArray
    //                 | InlineTable
    //             //     | TDateTime
    //                 | TFloat
    //                 | TInteger

    // SimpleKey   := QuotedKey
    //              | UnquotedKey
    // UnquotedKey := id: cangjie.Identifier { id.value }

    // // Quoted and dotted key
    // QuotedKey := BasicString 
    //     //        | LiteralString
    // DottedKey := (parts: SimpleKey["."...]+) { String.join(parts, delimiter: ".") }

    // // String
    // TString := mbs: MultilineBasicString { TOMLString(mbs) }
    //          | bs: BasicString { TOMLString(bs) }

    // // Basic String
    // BasicString := (s: cangjie.StringLiteral) { s.value }

    // // Multiline Literal String
    // MultilineBasicString := ~! "'" (ms: cangjie.MultilineString) { ms.value }

    // // Integer
    // TInteger := (i: cangjie.IntegerLiteral) { TOMLInteger(Int64.parse(i.value)) }

    // // Float
    // TFloat := (f: cangjie.FloatLiteral) { TOMLFloat(Float64.parse(f.value)) } 
    //         | SpecialFloat
    
    // SpecialFloat := "inf" { TOMLFloat(Float64.Inf) }
    //               | "nan" { TOMLFloat(Float64.NaN) }

    // Boolean
    TBoolean := "true" { TOMLBoolean(true) }
             | "false" { TOMLBoolean(false) }

    // // TODO: Date and Time (as defined in RFC 3339)

    // // Array
    // TArray := "[" (vals: Val[","...]*) "]" { TOMLArray(vals) }

    // // Table
    // Table := StdTable
    //        | ArrayTable

    // // Standard Table
    // StdTable := "[" k: Key "]" { TOMLStdTable(k) }

    // // Inline Table
    // InlineTable := "{" (kvs: KeyVal[","...]*) "}" { TOMLInlineTable(kvs) }

    // // Array Table
    // ArrayTable := "[[" k: Key "]]" { TOMLArrayTable(k) }
]
func ToTOML(input: TOMLValue): Tokens {
    input.toTokens()
}