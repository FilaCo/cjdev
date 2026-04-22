package result_cj

import std.collection.*

public enum Result<T, E> <: Iterable<T> where E <: ToString {
    Ok(T) | Err(E)

    public func isOk(): Bool {
        isOk {_ => true}
    }

    public func isOk(p: (T) -> Bool): Bool {
        match (this) {
            case Ok(v) => p(v)
            case _ => false
        }
    }

    public func isErr(): Bool {
        isErr {_ => true}
    }

    public func isErr(p: (E) -> Bool): Bool {
        match (this) {
            case Err(e) => p(e)
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

    public func map<R>(f: (T) -> R): Result<R, E> {
        match (this) {
            case Ok(v) => Ok(f(v))
            case Err(e) => Err(e)
        }
    }

    public func mapErr<U>(f: (E) -> U): Result<T, U> where U <: ToString {
        match (this) {
            case Ok(v) => Ok(v)
            case Err(e) => Err(f(e))
        }
    }

    public func expect(msg: String): T {
        match (this) {
            case Ok(v) => v
            case _ => throw Exception(msg)
        }
    }

    public func unwrap(): T {
        match (this) {
            case Ok(v) => v
            case Err(e) => throw Exception(e.toString())
        }
    }
}

extend<T, E> Result<T, E> where T <: ToString, E <: ToString {
    public func unwrapErr(): E {
        match (this) {
            case Err(e) => e
            case Ok(v) => throw Exception(v.toString()) // TODO: custom exception
        }
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
