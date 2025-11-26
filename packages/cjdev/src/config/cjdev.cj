package cjdev.config

import stdx.serialization.serialization.{Serializable, DataModel, DataModelStruct, field}

public struct CjDevConfig {
    public CjDevConfig(public let useDocker: Bool) {}
}

extend CjDevConfig <: Serializable<CjDevConfig> {
    public func serialize(): DataModel {
        DataModelStruct().add(field("useDocker", useDocker))
    }

    // throws CjDevConfigUnsupportedDataModelException
    public static func deserialize(dm: DataModel): CjDevConfig {
        let dms = match (dm) {
            case d: DataModelStruct => d
            case _ => throw CjDevConfigUnsupportedDataModelException()
        }
        CjDevConfig(Bool.deserialize(dms.get("useDocker")))
    }
}

public class CjDevConfigUnsupportedDataModelException <: Exception {
    public CjDevConfigUnsupportedDataModelException() {
        super("Unsupported DataModel class used, expected DataModelStruct")
    }
}
