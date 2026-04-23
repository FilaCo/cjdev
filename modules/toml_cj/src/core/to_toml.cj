package toml_cj.core

public interface ToTOML {
    func toTOML(): TOMLValue
}

extend String <: ToTOML {
    public func toTOML(): TOMLValue {
        TOMLString(this)
    }
}

extend Bool <: ToTOML {
    public func toTOML(): TOMLValue {
        TOMLBoolean(this)
    }
}

extend Array<TOMLValue> <: ToTOML {
    public func toTOML(): TOMLValue {
        TOMLArray(this)
    }
}

extend Float16 <: ToTOML {
    public func toTOML(): TOMLValue {
        TOMLFloat(Float64(this))
    }
}

extend Float32 <: ToTOML {
    public func toTOML(): TOMLValue {
        TOMLFloat(Float64(this))
    }
}

extend Float64 <: ToTOML {
    public func toTOML(): TOMLValue {
        TOMLFloat(this)
    }
}
