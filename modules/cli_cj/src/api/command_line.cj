package cli_cj.api

import cli_cj.core.{App, Builder}

public func commandLine(): AppBuilder {
    App.builder()
}

public func Positional<T>(default!: ?T = None, help!: ?String = None): T {
    throw Exception("Invalid usage. Positional can appear only under @Callback or @Command macro")
}

public func Optional<T>(shortName!: ?Rune = None, longName!: ?String = None, default!: ?T = None, help!: ?String = None): T {
    throw Exception("Invalid usage. Optional can appear only under @Callback or @Command macro")
}
