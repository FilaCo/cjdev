macro package toml_cj.macros

import std.ast.*
import std.convert.*
import dslkit.macros.*
public import toml_cj.support.*

/**
 * [TOML v1.1.0 grammar](https://github.com/toml-lang/toml/blob/1.1.0/toml.abnf)
 */
@GrammarMacro[
    Main := Value

    Value -> TOMLValue := TString
                        | TBoolean
                        | TArray
                        | InlineTable
                        // | Datetime
                        | TFloat
                        | TInteger
                        | Interpolated

    // String
    TString := mls: MultilineLiteralString { TOMLString(mls) }
             | ls: LiteralString { TOMLString(ls) }
             | mbs: MultilineBasicString { TOMLString(mbs) }
             | bs: BasicString { TOMLString(bs) }
    
    MultilineLiteralString := ~ "'" ms: cangjie.MultilineString { TOMLMultilineLiteralString(ms.value) }
    LiteralString          := ~ "'" ls: cangjie.StringLiteral { TOMLLiteralString(ls.value) }
    MultilineBasicString   := ms: cangjie.MultilineString { TOMLMultilineBasicString(ms.value) }
    BasicString            := ls: cangjie.StringLiteral { TOMLBasicString(ls.value) }

    // Boolean
    TBoolean := "true" { TOMLBoolean(true) }
              | "false" { TOMLBoolean(false) }

    // TODO: Date and Time (as defined in RFC 3339)

    // Array
    TArray := "[" values: Value[","...]* "]" { TOMLArray(values) }

    // Inline Table
    InlineTable := "{" kvs: KeyValue[","...]* "}" { TOMLInlineTable(kvs) }

    // Key-Value pairs
    KeyValue       := k: Key "=" v: Value { TOMLKeyValueData(key: k, value: v) }
    Key -> TOMLKey := SimpleKey 
                    | DottedKey
    
    SimpleKey -> TOMLSimpleKey := QuotedKey
                                | UnquotedKey
    UnquotedKey := id: cangjie.Identifier { TOMLUnquotedKey(id.value) }

    // Quoted and dotted key
    QuotedKey := bs: BasicString { TOMLQuotedKey(bs) }
               | ls: LiteralString { TOMLQuotedKey(ls) }
    DottedKey := parts: SimpleKey["."...]+ { TOMLDottedKey(parts) }

    // Integer
    TInteger := i: cangjie.IntegerLiteral { TOMLInteger(Int64.parse(i.value)) }

    // Float
    TFloat := f: cangjie.FloatLiteral { TOMLFloat(Float64.parse(f.value)) }

    Interpolated := id: cangjie.DollarIdentifier { TOMLInterpolated(dedollar(id)) }
                  | "$(" embed: cangjie.Expr ")" { TOMLInterpolated(embed.toTokens()) }
]
func TOMLValue2(input: TOMLValue): Tokens {
    input.toTokens()
}

func dedollar(dollarToken: Token): Tokens {
    let curPos = dollarToken.pos
    Tokens(Token(IDENTIFIER, dollarToken.value[1..]).addPosition(curPos.fileID, curPos.line, curPos.column))
}