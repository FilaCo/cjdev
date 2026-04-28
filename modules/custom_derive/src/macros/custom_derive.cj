macro package custom_derive.macros

import std.ast.*
import custom_derive.support.*
import std.collection.*

public macro CustomDerive(attrs: Tokens, input: Tokens): Tokens {
    let derivings = match (parseDerivingsList(attrs)) {
        case Ok(derivings) => derivings
        case Err(e) => 
            diagReport(ERROR, attrs, "invalid derivings list", e)
            return input
    }

    derivings.reverse()
    var tokens = input
    for (deriving in derivings) {
        tokens = quote(@$deriving($tokens))
    }
    tokens
}
