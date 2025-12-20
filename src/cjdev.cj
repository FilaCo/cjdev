package cjdev

import std.env.atExit
import stdx.log.{setGlobalLogger, Logger}
import registry.{Registry, Builder, extra.entry.AddLazy, extra.entry.AddTransient}
import cjdev.commands.{CjDevCommand, DcCommand}
import cjdev.logging.createGlobalLogger

/**
 * CjDev immutable service locator.
 * MUST be used only in the file its declared.
 */
private let REGISTRY: Registry = Registry
    .builder()
    .addLazy<CjDevCommand> {reg => CjDevCommand(reg.get<DcCommand>(), reg.get<Logger>())}
    .addLazy<DcCommand> {reg => DcCommand(reg.get<Logger>())}
    .addLazy<Logger>("cjdev.logger.global") {
        _ => createGlobalLogger()
    }
    .build()

/**
 * CjDev entrypoint.
 * Sets environment, logging, `atExit` callback and executes `CjDevCommand`
 */
public func cjDev(args: Array<String>): Unit {
    let logger = REGISTRY.get<Logger>("cjdev.logger.global")
    setGlobalLogger(logger)
    atExit {=> logger.close()}
    REGISTRY.get<CjDevCommand>().execute(args)
}
