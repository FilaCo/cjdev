"""Composition root: assembles the executor stack, the git adapter and the use cases.

It exists so that `commands/` stays wiring only (architecture decision 6) and so the
same assembly can be exercised in tests without going through Typer.
"""
