package cjdev.config

import std.collection.HashMap
import stdx.serialization.serialization.{Serializable, DataModel, DataModelStruct, field}

public struct CjDevConfig {
    public CjDevConfig(public let container!: ContainerConfig = ContainerConfig(),
        public let projects!: HashMap<String, ProjectConfig> = HashMap()) {}
}

extend CjDevConfig <: Serializable<CjDevConfig> {
    public func serialize(): DataModel {
        DataModelStruct().add(field("container", container)).add(field("projects", projects))
    }

    /** 
     * throws CjDevConfigUnsupportedDataModelException
     */
    public static func deserialize(dm: DataModel): CjDevConfig {
        let dms = match (dm) {
            case d: DataModelStruct => d
            case _ => throw CjDevConfigUnsupportedDataModelException()
        }
        CjDevConfig(container: ContainerConfig.deserialize(dms.get("container")),
            projects: HashMap<String, ProjectConfig>.deserialize(dms.get("projects")))
    }
}

public class CjDevConfigUnsupportedDataModelException <: Exception {
    public CjDevConfigUnsupportedDataModelException() {
        super("Unsupported DataModel class used, expected DataModelStruct")
    }

    protected func getClassName() {
        "CjDevConfigUnsupportedDataModelException"
    }
}
