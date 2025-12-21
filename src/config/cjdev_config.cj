package cjdev.config

import stdx.serialization.serialization.{Serializable, DataModel, DataModelStruct, field}
import cjdev.utils.Default

public struct CjDevConfig {
    public CjDevConfig(public let general: GeneralConfig, public let projects: ProjectsConfig) {}
}

extend CjDevConfig <: Default<CjDevConfig> {
    public func default(): CjDevConfig {
        CjDevConfig(GeneralConfig.default(), ProjectsConfig.default())
    }
}

extend CjDevConfig <: Serializable<CjDevConfig> {
    public func serialize(): DataModel {
        DataModelStruct().add(field("general", general)).add(field("projects", projects))
    }

   /** 
    * throws CjDevConfigUnsupportedDataModelException
    */ 
    public static func deserialize(dm: DataModel): CjDevConfig {
        let dms = match (dm) {
            case d: DataModelStruct => d
            case _ => throw CjDevConfigUnsupportedDataModelException()
        }
        CjDevConfig(GeneralConfig.deserialize(dms.get("general")), ProjectsConfig.deserialize(dms.get("projects")))
    }
}

public class CjDevConfigUnsupportedDataModelException <: Exception {
    public CjDevConfigUnsupportedDataModelException() {
        super("Unsupported DataModel class used, expected DataModelStruct")
    }
}
