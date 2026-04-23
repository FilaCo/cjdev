protected package cli_cj.core

import std.collection.*
import result_cj.*

public class App {
    public static func builder(): Builder {
        Builder()
    }

    public operator func ()(): Unit {
    }
}

public class Builder {
    public Builder() {
    }

    public func build(): Result<App, BuildError> {
        Ok(App())
    }

    public func add(builder: Builder, name!: ?String = None, help!: ?String = None): This {
        this
    }

    public operator func ()(): Unit {
        // TODO: Handle AppBuildError
        build().map {app: App => app()}.unwrap()
    }
}

public type BuildError = String
