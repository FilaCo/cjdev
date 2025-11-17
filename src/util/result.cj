package cjdev.util

public enum Result<T, E> {
    Ok(T)
    | Err(E)
}
