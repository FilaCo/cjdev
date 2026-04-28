package custom_derive

import std.unittest.*
import std.unittest.testmacro.*
import std.ast.*
import custom_derive.macros.*
import custom_derive.testing_macros.*

@Test
class CustomDeriveTest {
    @TestCase
    func testSmoke() {
        // arrange
        let input = quote(struct Foo {})
        let expected = quote(@D(@B(@A(struct Foo {}))))

        // act
        let actual = quote(@CustomDerive[A, B, D]($input))

        // assert
        @PowerAssert(expected.toString(), actual.toString())
    }
}