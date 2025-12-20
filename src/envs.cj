package cjdev

import std.env.getVariable

protected let CJDEV_LOG_DIR = getVariable("CJDEV_LOG_DIR").getOrDefault {=> "logs"}
protected let CJDEV_LOG_LEVEL = getVariable("CJDEV_LOG_LEVEL").getOrDefault {=> "info"}
