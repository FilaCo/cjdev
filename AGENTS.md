# AGENTS.md

Cangjie language workspace for Cangjie SDK developer utilities.

## Cangjie language

See [Cangjie Reference](~/Projects/skills/cangjie-agents-info/AGENTS.md) for Cangjie language reference.

## Environment

Requires Cangjie SDK 1.0.5. Set these environment variables:

```
CANGJIE_HOME=/path/to/.cangjie
CANGJIE_PATH=$CANGJIE_HOME/bin:$CANGJIE_HOME/tools/bin:~/.cjpm/bin
CANGJIE_LD_LIBRARY_PATH=$CANGJIE_HOME/runtime/lib/linux_x86_64_cjnative:$CANGJIE_HOME/tools/lib
```

## Build System

Uses `cjpm` (Cangjie Package Manager). Root `cjpm.toml` defines a workspace with 5 members.

```bash
cjpm build    # Build all workspace members
cjpm test     # Run tests
```

## Workspace Structure

| Module | Output Type | Purpose |
|--------|-------------|---------|
| `cjdev` | executable | Main CLI tool |
| `cli_cj` | dynamic | CLI argument library |
| `custom_derive` | dynamic | Macro/derive support |
| `pp` | dynamic | Pretty printing |
| `result_cj` | dynamic | Result type |
| `toml_cj` | dynamic | TOML parser |
| `survey` | dynamic | Survey functionality |

## Testing

Uses `std.unittest.*` with annotations:

```cangjie
@Test
class MyTest {
    @TestCase
    func testSomething() {
        @Expect(expected, actual)
        @AssertThrows(SomeException, someCall())
    }
}
```

Test file naming: `*_test.cj`

## Git Conventions

- Conventional commits required (enforced via commitlint + husky)
- Use `npm run prepare` after clone to install git hooks
- Commitizen available: `npx cz` for guided commits

## SDK Build Dependency Order

When building the full Cangjie SDK (not this repo):

```
cjc, rt → std → stdx → cjpm
```

## Container Builds

`assets/Dockerfile.in` defines containerized build environment with:

- Ubuntu 22.04 base
- Clang 15, CMake 3.26, GNUStep
- Java 17 for interop
