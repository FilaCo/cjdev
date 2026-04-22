package toml_cj.core

import std.unittest.*
import std.unittest.testmacro.*

@Test
class GrammarTest {
    @TestCase
    func smoke() {
        // arrange
        let expected = TOMLFile([TOMLStdTable("cangjie"), TOMLKeyVal(TOMLKeyValData("isSuper", TOMLBoolean(true)))])

        // act
        let ParseSuccess(actual, _) = TOML.File("""
[cangjie]
isSuper = true
""")
        // assert
        @PowerAssert(expected == actual)
    }
}
