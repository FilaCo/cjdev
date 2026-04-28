package result_cj

import std.collection.*

public enum Result<T, E> <: Iterable<T> where E <: ToString {
    Ok(T) | Err(E)

    public func isOk(): Bool {
        isOk {_ => true}
    }

    public func isOk(predicate: (T) -> Bool): Bool {
        match (this) {
            case Ok(v) => predicate(v)
            case _ => false
        }
    }

    public func isErr(): Bool {
        isErr {_ => true}
    }

    public func isErr(predicate: (E) -> Bool): Bool {
        match (this) {
            case Err(e) => predicate(e)
            case _ => false
        }
    }

    public func ok(): ?T {
        match (this) {
            case Ok(v) => v
            case Err(_) => None
        }
    }

    public func err(): ?E {
        match (this) {
            case Ok(_) => None
            case Err(e) => e
        }
    }

    public func iterator(): Iterator<T> {
        OptionIterator(ok())
    }

    public func errIterator(): Iterator<E> {
        OptionIterator(err())
    }

    public func map<R>(transform: (T) -> R): Result<R, E> {
        match (this) {
            case Ok(v) => Ok(transform(v))
            case Err(e) => Err(e)
        }
    }

    public func mapErr<U>(transform: (E) -> U): Result<T, U> where U <: ToString {
        match (this) {
            case Ok(v) => Ok(v)
            case Err(e) => Err(transform(e))
        }
    }

    public func expect(msg: String): T {
        match (this) {
            case Ok(v) => v
            case Err(e) => throw Exception("${msg}\nCause: ${e}") // TODO: custom exception
        }
    }

    public func unwrap(): T {
        match (this) {
            case Ok(v) => v
            case Err(e) => throw Exception(e.toString()) // TODO: custom exception
        }
    }

    public func unwrapErr(): E {
        match (this) {
            case Err(e) => e
            case Ok(v) => throw Exception() // TODO: custom exception
        }
    }

    public func unwrapOr(op: (E) -> T): T {
        match (this) {
            case Ok(v) => v
            case Err(e) => op(e)
        }
    }

    public func unwrapOr(default: T): T {
        unwrapOr {_ => default}
    }
}

class OptionIterator<T> <: Iterator<T> {
    private var isValRead = false
    public OptionIterator(private let val: ?T) {}

    public func next(): ?T {
        match (isValRead) {
            case false =>
                isValRead = true
                val
            case _ => None
        }
    }
}
