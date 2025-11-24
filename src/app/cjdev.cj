package cjdev.app

import cjdev.app.cli.CJDEV_CMD

public class CjDev {
    public func run(): Unit {
        CJDEV_CMD.build()
    }
}
