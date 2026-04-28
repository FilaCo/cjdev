package custom_derive.support

import std.ast.*
import std.unittest.*
import std.unittest.testmacro.*
import result_cj.*

@Test
class ParseDerivingsListTest {
    @TestCase
    func zeroDerivings() {
        // arrange
        let input = quote()
    
        // act
        let actual = parseDerivingsList(input)
    
        // assert
        @PowerAssert("ParseFailureException: Parse failed", actual.unwrapErr())
    }

    @TestCase
    func oneDeriving() {
        // arrange
        let input = quote(Foo)
        let expectedToken = Token(IDENTIFIER, "Foo")

        // act
        let actual = parseDerivingsList(input)

        // assert
        @Expect(actual.isOk())
        let unwrapped = actual.unwrap()
        @Expect(1, unwrapped.size)
        let actualToken = unwrapped[0]
        @Expect(expectedToken.kind == actualToken.kind)
        @Expect(expectedToken.value, actualToken.value)
    }

    @TestCase
    func moreThanOneDeriving() {
        // arrange
        let input = quote(Foo, Bar, Baz)
        let expected = [Token(IDENTIFIER, "Foo"), Token(IDENTIFIER, "Bar"), Token(IDENTIFIER, "Baz")]

        // act
        let actual = parseDerivingsList(input)

        // assert
        @Expect(actual.isOk())
        let unwrapped = actual.unwrap()
        @Expect(expected.size, unwrapped.size)
        for (i in 0..unwrapped.size) {
            @Expect(expected[i].kind == unwrapped[i].kind)
            @Expect(expected[i].value, unwrapped[i].value)
        }
    }
}
