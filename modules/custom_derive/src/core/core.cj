package custom_derive.core

import std.ast.*
import dslkit.macros.*

@Grammar[Derivings](
    List     := Deriving[","...]+
    Deriving := cangjie.Identifier
)
