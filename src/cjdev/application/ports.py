"""The ports the use cases require: `Executor` and `Git`.

They live here rather than in `domain/` because they are not domain concepts, yet the
application must depend on them without importing `infra`. Split into a package once
`forge` and `ccache` arrive and this file starts getting in the way.
"""
