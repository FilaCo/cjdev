"""Reading and writing `cjdev.lock` (decision 4).

Machine-owned and rewritten on every branch and sync operation, but TOML like the rest
so a human can read a diff of it. Converts to `domain.lock` types at the boundary — no
`TOMLDocument` leaves this module.
"""
