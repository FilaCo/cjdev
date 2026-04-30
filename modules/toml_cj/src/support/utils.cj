protected package toml_cj.support

import std.ast.*

@When[os == "Windows"]
let NL: String = "\r\n"
@When[os == "Linux"]
let NL: String = "\n"

protected func joinTokens<CollectionT, ItemT>(c: CollectionT, open!: Tokens = Tokens(), close!: Tokens = Tokens(),
    sep!: Tokens = Tokens()): Tokens where CollectionT <: Iterable<ItemT>, ItemT <: ToTokens {
    let result = open
    let iter = c.iterator()
    if (let Some(first) <- iter.next()) {
        result.append(first.toTokens())
    } else {
        result.append(close)
        return result
    }

    for (e in iter) {
        result.append(sep)
        result.append(e.toTokens())
    }

    result.append(close)
    return result
}

protected func joinTokens<CollectionT, ItemT>(c: CollectionT, open!: Tokens = Tokens(), close!: Tokens = Tokens(),
    sep!: Tokens = Tokens(), transform!: (ItemT) -> Tokens): Tokens where CollectionT <: Iterable<ItemT> {
    let result = open
    let iter = c.iterator()
    if (let Some(first) <- iter.next()) {
        result.append(transform(first))
    } else {
        result.append(close)
        return result
    }

    for (e in iter) {
        result.append(sep)
        result.append(transform(e))
    }

    result.append(close)
    return result
}
