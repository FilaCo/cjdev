package cjdev.app

import cjdev.util.cli.{Command}

public class CjDev {
    public CjDev() {
        let cmd = Command("cjdev")
            .withVersion("0.1.0")
            .withArgument {argument => argument}
            .withArgument {argument => argument}
    }
}
