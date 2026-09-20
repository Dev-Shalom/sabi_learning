"""Accounts: credentials, sessions, recovery codes and login throttling.

An account is credentials set on an identity that already exists, not a new
row. See `sabi.models.User` for why, and `identity.resolve_identity` for the
single place a request's identity is decided.
"""
