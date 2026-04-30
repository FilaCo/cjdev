package toml_cj

import std.unittest.*
import std.unittest.testmacro.*
import toml_cj.macros.*

@Test
class TOMLTest {
    @TestCase
    func smoke() {
        // arrange
        // act
        println(@TOMLValue2(
{ cangjie = "rules", check = true }

))
        // assert
        @Assert(1, 2)
    }
}