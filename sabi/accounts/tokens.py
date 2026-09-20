"""Keyed tokens: the CSRF token, and the signature on the anonymous id cookie.

Both are HMACs under `SABI_SECRET_KEY`, so rotating that key invalidates every
open form and every anonymous cookie at once -- which is what you want from a
leaked key, and is the reason they share one secret.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from sabi.config import settings


def _key() -> bytes:
    return settings().secret_key.encode("utf-8")


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def salted_hash(value: str, salt: str) -> str:
    """One-way, salted. Used for addresses and IPs in the throttle table."""
    return hashlib.sha256((salt + value).encode("utf-8")).hexdigest()[:48]


def sign(value: str) -> str:
    """`value.signature` -- a tamper-evident cookie value."""
    mac = hmac.new(_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{value}.{mac}"


def unsign(signed: str | None) -> str | None:
    """The original value, or None if it was absent, malformed or tampered."""
    if not signed or "." not in signed:
        return None
    value, _, mac = signed.rpartition(".")
    if not value or not mac:
        return None
    expected = hmac.new(_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(mac, expected):
        return None
    return value


def csrf_token(secret: str) -> str:
    """A token bound to one session -- or, for a visitor with no session, to
    their anonymous id. Anonymous visitors post too (asking a question spends
    an allowance and writes a row), so they are covered as well."""
    return hmac.new(_key(), secret.encode("utf-8"), hashlib.sha256).hexdigest()[:40]


def csrf_ok(secret: str, submitted: str | None) -> bool:
    if not submitted:
        return False
    return hmac.compare_digest(csrf_token(secret), submitted)


def new_session_token() -> str:
    """The value that goes in the cookie. Only its hash is ever stored."""
    return secrets.token_urlsafe(32)
