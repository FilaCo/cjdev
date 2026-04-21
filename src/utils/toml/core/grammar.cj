package cjdev.utils.toml.core

import std.ast.*
import std.convert.*
import dslkit.macros.*
import dslkit.token_parsers.*

/**
 * [TOML v1.1.0 grammar](https://github.com/toml-lang/toml/blob/1.1.0/toml.abnf), but with the following exceptions:
 * 1. Cangjie comments are allowed (due to DSLKit design).
 * 2. Kebab-cased unquoted keys are not supported.
 * 3. Literal strings (enclosed by `'`) are not supported.
 * 4. Multiline literal strings (enclosed by `'''`) are not supported.
 * 5. DateTime is not supported.
 */
@Grammar[public TOML](
    // Overall Structure
    File := (exprs: Expr[cangjie.NL...]+) cangjie.EOF { TOMLFile(exprs) }

    Expr := (kv: KeyVal) Comment? { TOMLKeyVal(kv) }
          | (t: Table) Comment? { t }

    // Comment
    Comment := "#" ~! cangjie.NL { () }

    // Key-Value pairs
    KeyVal := (k: Key) "=" (v: Val) { TOMLKeyValData(k, v) }
    Key    := SimpleKey
            | DottedKey

    Val -> TOMLVal := TString
                    | Boolean
                    | TArray
                    | InlineTable
                //     | TDateTime
                    | TFloat
                    | TInteger

    SimpleKey   := QuotedKey
                 | UnquotedKey
    UnquotedKey := id: cangjie.Identifier { id.value }

    // Quoted and dotted key
    QuotedKey := BasicString 
        //        | LiteralString
    DottedKey := (parts: SimpleKey["."...]+) { String.join(parts, delimiter: ".") }

    // String
    TString := mbs: MultilineBasicString { TOMLString(mbs) }
             | bs: BasicString { TOMLString(bs) }

    // Basic String
    BasicString := (s: cangjie.StringLiteral) { s.value }

    // Multiline Literal String
    MultilineBasicString := ~! "'" (ms: cangjie.MultilineString) { ms.value }

    // Integer
    TInteger := (i: cangjie.IntegerLiteral) { TOMLInteger(Int64.parse(i.value)) }

    // Float
    TFloat := (f: cangjie.FloatLiteral) { TOMLFloat(Float64.parse(f.value)) } 
            | SpecialFloat
    
    SpecialFloat := "inf" { TOMLFloat(Float64.Inf) }
                  | "nan" { TOMLFloat(Float64.NaN) }

    // Boolean
    Boolean := "true" { TOMLBoolean(true) }
             | "false" { TOMLBoolean(false) }

    // TODO: Date and Time (as defined in RFC 3339)

    // Array
    TArray := "[" (vals: Val[","...]*) "]" { TOMLArray(vals) }

    // Table
    Table := StdTable
           | ArrayTable

    // Standard Table
    StdTable := "[" k: Key "]" { TOMLStdTable(k) }

    // Inline Table
    InlineTable := "{" (kvs: KeyVal[","...]*) "}" { TOMLInlineTable(kvs) }

    // Array Table
    ArrayTable := "[[" k: Key "]]" { TOMLArrayTable(k) }
)
