"""Pure core: data and functions over it, no I/O.

Deliberately re-exports nothing. `domain/` is a layer boundary, not a facade -
callers import the module they mean (`from cjdev.domain.manifest import ...`),
so that what depends on what stays visible in the import lines.
"""
