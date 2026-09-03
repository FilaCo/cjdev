"""Executor construction.

Exposes `build_executor` and hides the decorator order. The stack is dry-run over
logging over host, so UX-1 and UX-3 are implemented once and no command path can
bypass them (ENV-1). This is the one subpackage here that earns its `__init__`: what it
hides is the wrapping order.
"""
