package cjdev.env

import std.env.getVariable

public let CJDEV_LOG_DIR: String = getVariable("CJDEV_LOG_DIR").getOrDefault {=> "logs"}
public let CJDEV_LOG_LEVEL: String = getVariable("CJDEV_LOG_LEVEL").getOrDefault {=> "info"}
