protected package toml_cj.support

public interface ToTOMLValue {
    func toTOMLValue(): TOMLValue
}

public func toTOMLValue<T>(toml: T): TOMLValue where T <: ToTOMLValue {
    toml.toTOMLValue()
}
