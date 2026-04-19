macro package cjdev.utils.cli.macros

import std.ast.*

public macro Command(input: Tokens): Tokens {
    input
}

public macro Command(_: Tokens, input: Tokens): Tokens {
    input
}