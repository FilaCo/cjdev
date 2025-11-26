package cjdev.domain.dc.aggregate_root

import cjdev.domain.dc.vo.UseDocker
import stdx.logger.Logger

public class Dc {
    public Dc(private let logger: Logger) {}
    public func initContainer() {
    }
    public func runCommand() {}
}
