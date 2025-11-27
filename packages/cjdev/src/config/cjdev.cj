package cjdev.config

import std.fs.{exists, Path}
import stdx.serialization.serialization.{Serializable, DataModel, DataModelStruct, field}
import yadi.{RegistryBuilder, Registry}
import cangjie_toml.cangjie_toml.FromToml

public struct CjDevConfig {
    public CjDevConfig(public let general: GeneralConfig, public let projects: ProjectsConfig) {}
}

extend CjDevConfig <: Serializable<CjDevConfig> {
    public func serialize(): DataModel {
        DataModelStruct().add(field("general", general)).add(field("projects", projects))
    }

    // throws CjDevConfigUnsupportedDataModelException
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

public func addConfig(builder: RegistryBuilder): RegistryBuilder {
    const CJDEV_CONFIG_PATH = "cjdev.toml"
    if (!exists(CJDEV_CONFIG_PATH)) {
        return builder
    }

    builder
        .addLazy<CjDevConfig> {
            _ => DataModel.fromTomlFile(CJDEV_CONFIG_PATH) |> CjDevConfig.deserialize
        }
        .addTransient<GeneralConfig> {
            reg => reg.get<CjDevConfig>().general
        }
        .addTransient<ProjectsConfig> {reg => reg.get<CjDevConfig>().projects}
}
