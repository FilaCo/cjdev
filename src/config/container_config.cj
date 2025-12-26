package cjdev.config

import std.collection.ArrayList
import std.fs.Path
import stdx.serialization.serialization.{Serializable, DataModel, DataModelStruct, field}

public struct ContainerConfig {
    public ContainerConfig(public let useContainer!: Bool = false, public let hostWorkdir!: ?Path = None,
        public let containerWorkdir!: ?Path = None, public let containerName!: ?String = None) {
        check()
    }

    /**
     * throws InvalidContainerConfigException
     */
    public func check(): Unit {
        if (!useContainer) {
            return
        }

        var missingFields = ArrayList<String>()
        if (hostWorkdir.isNone()) {
            missingFields.add("host-workdir")
        }
        if (containerWorkdir.isNone()) {
            missingFields.add("container-workdir")
        }
        if (containerName.isNone()) {
            missingFields.add("container-name")
        }
        if (!missingFields.isEmpty()) {
            throw InvalidContainerConfigException(
                "missing required fields when `use-container = true`: ${missingFields}")
        }
    }
}

public class InvalidContainerConfigException <: Exception {
    public InvalidContainerConfigException(msg: String) {
        super(msg)
    }
    protected func getClassName() {
        "InvalidContainerConfigException"
    }
}

extend ContainerConfig <: Serializable<ContainerConfig> {
    public func serialize(): DataModel {
        DataModelStruct()
            .add(field("use-container", useContainer))
            .add(field("host-workdir", hostWorkdir.toString()))
            .add(field("container-workdir", containerWorkdir.toString()))
            .add(field("container-name", containerName.toString()))
    }

    /**
     * throws ContainerConfigUnsupportedDataModelException
     */
    public static func deserialize(dm: DataModel): ContainerConfig {
        let dms = match (dm) {
            case d: DataModelStruct => d
            case _ => throw ContainerConfigUnsupportedDataModelException()
        }

        ContainerConfig(
            useContainer: Bool.deserialize(dms.get("use-container")),
            hostWorkdir: Option<String>.deserialize(dms.get("host-workdir")).map {v: String => Path(v)},
            containerWorkdir: Option<String>.deserialize(dms.get("container-workdir")).map {v: String => Path(v)},
            containerName: Option<String>.deserialize(dms.get("container-name"))
        )
    }
}

public class ContainerConfigUnsupportedDataModelException <: Exception {
    public ContainerConfigUnsupportedDataModelException() {
        super("Unsupported DataModel class used, expected DataModelStruct")
    }
    protected func getClassName() {
        "ContainerConfigUnsupportedDataModelException"
    }
}
