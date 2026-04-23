macro package cli_cj

import std.ast.*

public macro Command(attrs: Tokens, input: Tokens): Tokens {
    input
}
