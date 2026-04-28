protected package cli_cj.core

import std.collection.*
import std.env.*
import result_cj.*

public class App {
    public static func builder(): AppBuilder {
        AppBuilder()
    }

    public operator func ()(args: ?Array<String>): Unit {
    }
}

public class AppBuilder {
    public AppBuilder() {
    }

    public func build(): Result<App, AppBuildError> {
        Ok(App())
    }

    public func add(builder: AppBuilder, name!: ?String = None, help!: ?String = None): AppBuilder {
        this
    }

    public func add<F>(command: F): AppBuilder {
        this
    }

    public func callback<F>(callback: F): AppBuilder {
        this
    }

    public operator func ()(args: ?Array<String>): Unit {
        // TODO: Handle AppBuildError
        build().map {app: App => app(args)}.unwrap()
    }
}

public type AppBuildError = String
