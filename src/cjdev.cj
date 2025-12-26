package cjdev

import std.argopt.{ArgumentParseException, parseArguments, ArgumentSpec, ArgumentMode, ParsedArguments}
import std.collection.{ArrayList, HashMap}
import std.env.{atExit, getWorkingDirectory, exit, getVariable}
import std.fs.{exists, Path}
import stdx.log.{setGlobalLogger, Logger, LogLevel}
import stdx.serialization.serialization.DataModel
import cangjie_toml.cangjie_toml.FromToml
import registry.{Registry, Builder, extra.entry.AddLazy, extra.entry.AddTransient}
import cjdev.config.{CjDevConfig, ContainerConfig, ProjectConfig}
import cjdev.features.{Dc, CommandLauncher, ContainerCommandLauncher, ContainerSettings}
import cjdev.logging.createGlobalLogger

private const CJDEV_CONFIG_PATH_TAG = "cjdev.config.path"
private const CJDEV_LOGGER_GLOBAL_TAG = "cjdev.logger.global"
private const CJDEV_LOG_DIR_TAG = "cjdev.log.dir"
private const CJDEV_COMMAND_LAUNCHER = "cjdev.commandLauncher"
private const CJDEV_COMMAND_LAUNCHER_CONTAINER = "cjdev.commandLauncher.container"

/**
 * CjDev immutable service locator.
 * MUST be used only in the file its declared.
 */
private let REGISTRY: Registry = Registry
    .builder()
    // features
    .addLazy<CjDev> {reg => CjDev(reg.get<Logger>(CJDEV_LOGGER_GLOBAL_TAG), reg.get<Dc>())}
    .addLazy<Dc> {reg => Dc(reg.get<Logger>(CJDEV_LOGGER_GLOBAL_TAG), reg.get<CommandLauncher>())}
    .addLazy<CommandLauncher> {
        reg =>
            let useContainer = reg.get<ContainerConfig>().useContainer
            if (useContainer) {
                ContainerCommandLauncher(reg.get<Logger>(CJDEV_LOGGER_GLOBAL_TAG), reg.get<ContainerSettings>())
            } else {
                reg.get<CommandLauncher>(CJDEV_COMMAND_LAUNCHER)
            }
    }
    .addLazy<CommandLauncher>(CJDEV_COMMAND_LAUNCHER) {_ => CommandLauncher()}
    .addLazy<ContainerSettings> {
        reg =>
            let containerCfg = reg.get<ContainerConfig>()
            ContainerSettings(hostWorkdir: containerCfg.hostWorkdir.map {p => p.normalize()}.getOrThrow(),
                containerWorkdir: containerCfg.containerWorkdir.map {p => p.normalize()}.getOrThrow(),
                containerName: containerCfg.containerName.getOrThrow())
    }
    // config
    .addLazy<Path>(CJDEV_CONFIG_PATH_TAG) {
        reg =>
            const CJDEV_CONFIG_FILE_NAME = "cjdev.toml"
            let logger = reg.get<Logger>(CJDEV_LOGGER_GLOBAL_TAG)
            var workDir = getWorkingDirectory()
            var configPath = workDir.join(CJDEV_CONFIG_FILE_NAME)
            let firstAttempt = configPath
            var attempts = ArrayList<String>()
            while (!exists(configPath)) {
                attempts.add(configPath.toString())
                if (workDir == Path("/")) {
                    break
                }
                workDir = workDir.parent
                configPath = workDir.join(CJDEV_CONFIG_FILE_NAME)
            }

            if (!exists(configPath)) {
                logger.warn("unable to find the config file", [("attempts", attempts.toArray())])
                return firstAttempt
            }

            configPath
    }
    .addLazy<CjDevConfig> {
        reg =>
            let logger = reg.get<Logger>(CJDEV_LOGGER_GLOBAL_TAG)
            let configPath = reg.get<Path>(CJDEV_CONFIG_PATH_TAG)
            if (!exists(configPath)) {
                logger.warn("config file does not exist, using default configuration",
                    ("configPath", configPath.toString()))
                return CjDevConfig()
            }

            try {
                DataModel.fromTomlFile(configPath) |> CjDevConfig.deserialize
            } catch (e: Exception) {
                logger.error("unable to parse the config file, using default configuration",
                    [("cause", e.message), ("configPath", configPath.toString())])
                return CjDevConfig()
            }
    }
    .addTransient<ContainerConfig> {
        reg => reg.get<CjDevConfig>().container
    }
    .addTransient<HashMap<String, ProjectConfig>> {
        reg => reg.get<CjDevConfig>().projects
    }
    // logging
    .addLazy<Path>(CJDEV_LOG_DIR_TAG) {_ => Path(getVariable("CJDEV_LOG_DIR").getOrDefault {=> "logs"})}
    .addLazy<Logger>(CJDEV_LOGGER_GLOBAL_TAG) {
        reg => createGlobalLogger(reg.get<Path>(CJDEV_LOG_DIR_TAG))
    }
    .build()

/**
 * CjDev entrypoint.
 * Sets environment, logging and `atExit` callback
 */
public func cjDev(args: Array<String>): Unit {
    let logger = REGISTRY.get<Logger>(CJDEV_LOGGER_GLOBAL_TAG)
    setGlobalLogger(logger)
    atExit {=> logger.close()}
    REGISTRY.get<CjDev>().execute(args)
}

private class CjDev {
    public CjDev(private let logger_: Logger, private let dc_: Dc) {}

    public func execute(args: Array<String>): Unit {
        try {
            let parsed = parseArguments(args, CJDEV_ARGS_SPEC)
            let options = parsed.options
            var nonOptions = parsed.nonOptions
            if (options.contains("version") || options.contains("V")) {
                printVersion()
                return
            }

            if (nonOptions.isEmpty()) {
                printHelp()
                return
            }

            let cmd = nonOptions[0]
            nonOptions = nonOptions[1..]
            match (cmd) {
                case "dc" => dc_.execute(options, nonOptions)
                // TODO: Exception
                case cmd => throw Exception("no such command: `${cmd}`")
            }
        } catch (e: Exception) {
            logger_.error(e.message)
            printUsage()
            exit(1)
        }
    }

    private static let CJDEV_ARGS_SPEC = [Full("version", r'V', NoValue), Full("verbose", r'v', NoValue),
        Full("help", r'h', NoValue)];
    private static const CJDEV_VERSION = "0.1.0"
    private static const CJDEV_USAGE = "Usage: cjdev [OPTIONS] <COMMAND>"
    private static let CJDEV_HELP = """
Cangjie's developer utility tool

${CJDEV_USAGE}

Options:
  -V, --version   Print version info and exit
  -v, --verbose   Use verbose output
  -h, --help      Print help

Commands:
  status    Show the cjdev environment status
  init, i   Init cjdev environment
  build     Build Cangjie's projects
  test      Test Cangjie's projects
  git       Git utils for Cangjie's repositories management
  dc        Execute a command in the container."""

    private func printHelp(): Unit {
        println(CJDEV_HELP)
    }

    private func printUsage(): Unit {
        println(CJDEV_USAGE)
    }

    private func printVersion(): Unit {
        println("cjdev ${CJDEV_VERSION}")
    }
}
