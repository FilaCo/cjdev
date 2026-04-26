protected package cli_cj.core

import std.convert.Parsable

sealed abstract class Argument<T> where T <: Parsable<T> {
    Argument(public let default!: ?T = None, public let help!: ?String = None) {}
}

class Positional<T> <: Argument<T> where T <: Parsable<T> {}

class Optional<T> <: Argument<T> where T <: Parsable<T> {
    Optional(default!: ?T = None, public let longName!: ?String = None, public let shortName!: ?Rune = None) {
        super(default: default)
    }
}
