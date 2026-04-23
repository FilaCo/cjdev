package toml_cj.core

public interface FromTOML<T> {
    static func fromTOML(value: TOMLValue): T
}
