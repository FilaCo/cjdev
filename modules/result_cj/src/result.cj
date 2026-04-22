package result_cj

public enum Result<T, E> where E <: Exception {
    Ok(T) | Err(E)

    public func unwrap(): T {
        match (this) {
            case Ok(v) => v
            case Err(e) => throw e
        }
    }

    public func unwrapErr(): E {
        match (this) {
            case Err(e) => e
            case Ok(v) => throw Exception() // TODO: custom exception
        }
    }
}
