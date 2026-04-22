package result_cj

public enum Result<T, E> {
    Ok(T) | Err(E)
}
