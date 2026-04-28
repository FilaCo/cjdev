protected package custom_derive.support

import std.ast.*
import result_cj.*
import dslkit.macros.*

protected func parseDerivingsList(input: Tokens): Result<Array<Token>, ParseDerivingsListError> {
    try {
        let ParseSuccess(list, _) = Derivings.List(input)
        Ok(list)
    } catch (e: Exception) {
        Err(e.toString())
    }
}

protected type ParseDerivingsListError = String

@Grammar[private Derivings](
    List     := Deriving[","...]+
    Deriving := cangjie.Identifier
)
