package toml_cj.core

import result_cj.*

public interface TryFromTOML<T> {
    static func tryFromTOML(value: TOMLValue): TryFromTOMLResult<T>
}

public type TryFromTOMLResult<T> = Result<T, TryFromTOMLError>

public type TryFromTOMLError = String
