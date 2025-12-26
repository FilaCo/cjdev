package cjdev.config

import std.collection.HashMap
import stdx.serialization.serialization.{Serializable, DataModel, DataModelStruct, field}
import cjdev.utils.Default

public struct ProjectConfig {
    public ProjectConfig(public let name!: String, public let path!: String, public let origin!: String,
        public let upstream!: String, public let branch!: String) {}
}

extend ProjectConfig <: Serializable<ProjectConfig> {
    public func serialize(): DataModel {
        DataModelStruct()
            .add(field("name", name))
            .add(field("path", path))
            .add(field("origin", origin))
            .add(field("upstream", upstream))
            .add(field("branch", branch))
    }

    /**
     * throws ProjectConfigUnsupportedDataModelException
     */
    public static func deserialize(dm: DataModel): ProjectConfig {
        let dms = match (dm) {
            case d: DataModelStruct => d
            case _ => throw ProjectConfigUnsupportedDataModelException()
        }
        ProjectConfig(name: String.deserialize(dms.get("name")), path: String.deserialize(dms.get("path")),
            origin: String.deserialize(dms.get("origin")), upstream: String.deserialize(dms.get("upstream")),
            branch: String.deserialize(dms.get("branch")))
    }
}

public class ProjectConfigUnsupportedDataModelException <: Exception {
    public ProjectConfigUnsupportedDataModelException() {
        super("Unsupported DataModel class used, expected DataModelStruct")
    }
    protected func getClassName() {
        "ProjectConfigUnsupportedDataModelException"
    }
}
