package cjdev.app.dto

import stdx.serialization.serialization.{Serializable, DataModel, DataModelBool}

public enum UseDockerDto {
    No | Yes
}

extend UseDockerDto <: Serializable<UseDockerDto> {
    public func serialize(): DataModel {
        DataModelBool(match (this) {
            case Yes => true
            case _ => false
        })
    }

    public static func deserialize(dm: DataModel): UseDockerDto {
        let dmb = match (dm) {
            case data: DataModelBool => data
            case _ => throw Exception("DataModelBool expected")
        }

        match (dmb.getValue()) {
            case true => Yes
            case _ => No
        }
    }
}
