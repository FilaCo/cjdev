package cjdev

import std.argopt.{ArgumentParseException, parseArguments, ArgumentSpec, ArgumentMode}
import std.env.{atExit, exit}
import stdx.log.{setGlobalLogger, Logger}
import registry.{Registry, Builder, extra.entry.AddLazy, extra.entry.AddTransient}
import cjdev.features.Dc
import cjdev.logging.createGlobalLogger

private const GLOBAL_LOGGER_TAG = "cjdev.logger.global"

/**
 * CjDev immutable service locator.
 * MUST be used only in the file its declared.
 */
private let REGISTRY: Registry = Registry
    .builder()
    .addLazy<CjDev> {reg => CjDev(reg.get<Dc>(), reg.get<Logger>(GLOBAL_LOGGER_TAG))}
    .addLazy<Dc> {reg => Dc(reg.get<Logger>(GLOBAL_LOGGER_TAG))}
    .addLazy<Logger>(GLOBAL_LOGGER_TAG) {
        _ => createGlobalLogger()
    }
    .build()

/**
 * CjDev entrypoint.
 * Sets environment, logging, `atExit` callback and executes `CjDevCommand`
 */
public func cjDev(args: Array<String>): Unit {
    let logger = REGISTRY.get<Logger>(GLOBAL_LOGGER_TAG)
    setGlobalLogger(logger)
    atExit {=> logger.close()}
    REGISTRY.get<CjDev>().execute(args)
}

private class CjDev {
    public CjDev(private let dc_: Dc, private let logger_: Logger) {}

    public func execute(args: Array<String>): Unit {
        logger_.trace("executing cjdev command...")
        try {
            let parsed = parseArguments(args, CJDEV_ARGS_SPEC)
        } catch (e: ArgumentParseException) {
            logger_.error("argument parsing failed")
            println(CJDEV_USAGE)
            exit(1)
        }
    }

    private static let CJDEV_ARGS_SPEC = [Full("version", r'V', NoValue), Full("verbose", r'v', NoValue),
        Full("help", r'h', NoValue)];
    private static const CJDEV_USAGE = "Usage: cjdev [OPTIONS] [COMMAND]"
    private static let CJDEV_HELP = """
Cangjie's developer utility tool

${CJDEV_USAGE}

Options:
  -V, --version   Print version info and exit
  -v, --verbose   Use verbose output
  -h, --help      Print help

Commands:
  init, i   Init cjdev environment
  build     Build Cangjie's projects
  test      Test Cangjie's projects
  git       Git utils for Cangjie's repositories management
  dc        Execute a command in the container.
"""
}
