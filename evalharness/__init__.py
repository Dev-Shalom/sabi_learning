"""The evaluation harness.

Kept as a separate top-level package rather than a subpackage of `sabi`, because
it must be able to treat the application as a black box: it calls the same
public entry point the web app calls, through the same limiter, with the same
config. An eval that reaches inside the system measures the system it imagined.
"""
