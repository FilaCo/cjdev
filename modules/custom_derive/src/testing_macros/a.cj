protected macro package custom_derive.testing_macros

import std.ast.*

public macro A(input: Tokens): Tokens {
    input
}