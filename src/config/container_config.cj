package cjdev.config

import stdx.serialization.serialization.{Serializable, DataModel, DataModelStruct, field}
import cjdev.utils.Default

public struct ContainerConfig {
  public ContainerConfig(public let useContainer!: Bool, public let containerWorkdir!: ?Path) {}
}

extend ContainerConfig <: Default<ContainerConfig> {
    public static func default(): ContainerConfig {
        ContainerConfig(useContainer: false, containerWorkdir: None)
    }
}

extend ContainerConfig <: Serializable<ContainerConfig> {
    public func serialize(): DataModel {
      DataModelStruct().add(field("use-container", useContainer)).add(field("container-workdir", containerWorkdir))
    }

    /**
     * throws ContainerConfigUnsupportedDataModelException
     */
    public static func deserialize(dm: DataModel): ContainerConfig {
        let dms = match (dm) {
            case d: DataModelStruct => d
            case _ => throw ContainerConfigUnsupportedDataModelException()
        }

        ContainerConfig(useContainer:  Bool.deserialize(dms.get("use-container"))) 
    }
}

public class ContainerConfigUnsupportedDataModelException <: Exception {
    public GeneralConfigUnsupportedDataModelException() {
        super("Unsupported DataModel class used, expected DataModelStruct")
    }
    protected func getClassName() {
        "ContainerConfigUnsupportedDataModelException"
    }
}
