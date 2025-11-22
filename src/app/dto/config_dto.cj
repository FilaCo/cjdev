package cjdev.app.dto

import stdx.serialization.serialization.{Serializable, DataModel, DataModelStruct, field}

public struct ConfigDto {
    public ConfigDto(public var useDocker!: UseDockerDto = UseDockerDto.No) {}
}

extend ConfigDto <: Serializable<ConfigDto> {
    public func serialize(): DataModel {
        DataModelStruct().add(field<UseDockerDto>("useDocker", useDocker))
    }

    public static func deserialize(dm: DataModel): ConfigDto {
        let dms = match (dm) {
            case data: DataModelStruct => data
            case _ => throw Exception("DataModelStruct expected")
        }

        ConfigDto(useDocker: UseDockerDto.deserialize(dms.get("useDocker")))
    }
}
