package cjdev.config

import std.collection.HashMap
import stdx.serialization.serialization.{Serializable, DataModel, DataModelStruct, field}

public struct ProjectsConfig {
    public ProjectsConfig(public let projects: HashMap<String, ProjectConfig>) {}
}

extend ProjectsConfig <: Serializable<ProjectsConfig> {
    public func serialize(): DataModel {
        var dms = DataModelStruct()

        for (project in projects.values()) {
            dms.add(field(project.name, project))
        }

        dms
    }

    // throws ProjectsConfigUnsupportedDataModelException
    public static func deserialize(dm: DataModel): ProjectsConfig {
        let dms = match (dm) {
            case d: DataModelStruct => d
            case _ => throw ProjectsConfigUnsupportedDataModelException()
        }

        var projects = HashMap<String, ProjectConfig>()
        for (field in dms.getFields()) {
            let project = ProjectConfig.deserialize(field.getData())
            projects.add(project.name, project)
        }

        ProjectsConfig(projects)
    }
}

public class ProjectsConfigUnsupportedDataModelException <: Exception {
    public ProjectsConfigUnsupportedDataModelException() {
        super("Unsupported DataModel class used, expected DataModelStruct")
    }
    protected func getClassName() {
        "ProjectsConfigUnsupportedDataModelException"
    }
}

public struct ProjectConfig {
    public ProjectConfig(public let name: String, public let path: String, public let origin: String,
        public let upstream: String, public let branch: String) {}
}

extend ProjectConfig <: Serializable<ProjectConfig> {
    public func serialize(): DataModel {
        DataModelStruct()
    }

    // throws ProjectConfigUnsupportedDataModelException
    public static func deserialize(dm: DataModel): ProjectConfig {
        let dms = match (dm) {
            case d: DataModelStruct => d
            case _ => throw ProjectConfigUnsupportedDataModelException()
        }
        ProjectConfig(String.deserialize(dms.get("name")), String.deserialize(dms.get("path")),
            String.deserialize(dms.get("origin")), String.deserialize(dms.get("upstream")),
            String.deserialize(dms.get("branch")))
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
