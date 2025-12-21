package cjdev.config

import stdx.serialization.serialization.{Serializable, DataModel, DataModelStruct, field}
import cjdev.utils.Default

public struct GeneralConfig {
    public GeneralConfig(public let useDocker: Bool) {}
}

extend GeneralConfig <: Default<GeneralConfig> {
    public func default(): GeneralConfig {
        GeneralConfig(false)
    }
}

extend GeneralConfig <: Serializable<GeneralConfig> {
    public func serialize(): DataModel {
        DataModelStruct().add(field("useDocker", useDocker))
    }

    /**
     * throws GeneralConfigUnsupportedDataModelException
     */
    public static func deserialize(dm: DataModel): GeneralConfig {
        let dms = match (dm) {
            case d: DataModelStruct => d
            case _ => throw GeneralConfigUnsupportedDataModelException()
        }
        GeneralConfig(Bool.deserialize(dms.get("useDocker")))
    }
}

public class GeneralConfigUnsupportedDataModelException <: Exception {
    public GeneralConfigUnsupportedDataModelException() {
        super("Unsupported DataModel class used, expected DataModelStruct")
    }
    protected func getClassName() {
        "GeneralConfigUnsupportedDataModelException"
    }
}
