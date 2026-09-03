"""Decorator that prints mutating commands instead of running them (UX-1).

Reads still execute: `init --dry-run` has to inspect the filesystem to say what it
would do. That is why `Command` carries a `mutates` flag.
"""
