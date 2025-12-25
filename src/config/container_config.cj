package cjdev.config

import stdx.serialization.serialization.{Serializable, DataModel, DataModelStruct, field}
import cjdev.utils.Default

public enum ContainerConfig {
    NoContainer
    | UseContainer(ContainerConfigData)
}

extend ContainerConfig <: Default<ContainerConfig> {
    public static func default(): ContainerConfig {
        NoContainer
    }
}

extend ContainerConfig <: Serializable<ContainerConfig> {
    public func serialize(): DataModel {
        match (this) {
            case NoContainer => 
          }
    }

    /**
     * throws ContainerConfigUnsupportedDataModelException
     */
    public static func deserialize(dm: DataModel): GeneralConfig {
        let dms = match (dm) {
            case d: DataModelStruct => ContainerConfigData()
            case _ => NoContainer
        }    
    }
}

public struct ContainerConfigData {
    public ContainerConfigData() {}
  }

public class ContainerConfigUnsupportedDataModelException <: Exception {
    public GeneralConfigUnsupportedDataModelException() {
        super("Unsupported DataModel class used, expected DataModelStruct")
    }
    protected func getClassName() {
        "ContainerConfigUnsupportedDataModelException"
    }
}
