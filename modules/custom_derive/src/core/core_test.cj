package custom_derive.core

import std.ast.*
import std.unittest.*
import std.unittest.testmacro.*

@Test
class DerivingsGrammarTest {
    @TestCase
    func zeroDerivings() {
        @AssertThrows(Derivings.List(quote()))
    }

    @TestCase
    func oneDeriving() {
        // arrange
        let expectedToken = Token(IDENTIFIER, "Foo")

        // act
        let ParseSuccess(actual, _) = Derivings.List(quote(Foo))

        // assert
        @Expect(1, actual.size)
        let actualToken = actual[0]
        @Expect(expectedToken.kind == actualToken.kind)
        @Expect(expectedToken.value, actualToken.value)
    }

    @TestCase
    func moreThanOneDeriving() {
        // arrange
        let expected = [Token(IDENTIFIER, "Foo"), Token(IDENTIFIER, "Bar"), Token(IDENTIFIER, "Baz")]

        // act
        let ParseSuccess(actual, _) = Derivings.List(quote(Foo, Bar, Baz))

        // assert
        @Expect(expected.size, actual.size)
        for (i in 0..actual.size) {
            @Expect(expected[i].kind == actual[i].kind)
            @Expect(expected[i].value, actual[i].value)
        }
    }
}
