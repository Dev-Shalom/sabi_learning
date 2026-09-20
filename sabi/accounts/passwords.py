"""Password hashing with scrypt from the standard library.

No new dependency, in keeping with how the rest of this project is built. The
parameters live inside the stored value, so they can be raised later and every
existing hash still verifies -- and a hash written today can be upgraded the
next time its owner logs in.

Two things here are easy to get wrong and are handled deliberately:

  - `maxmem`. scrypt's memory cost is 128 * r * n, which at n=2**14, r=8 is
    16 MiB. OpenSSL's default cap is 32 MiB, so raising n to 2**15 fails with
    "memory limit exceeded" rather than simply being slower. maxmem is passed
    explicitly so the failure is impossible rather than surprising.

  - Timing. Verifying against a real hash takes ~100ms and rejecting an unknown
    address takes none, which tells an attacker which addresses have accounts.
    `verify` against DUMMY_HASH costs the same as a real check.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

# 16 MiB and roughly 100ms on a small machine. Both numbers matter: the memory
# is what makes a GPU attack expensive, and the time is what a student waits.
N = 2**14
R = 8
P = 1
MAXMEM = 64 * 1024 * 1024
SALT_BYTES = 16
KEY_BYTES = 32

PREFIX = "scrypt"


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=MAXMEM,
        dklen=KEY_BYTES,
    )


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def hash_password(password: str) -> str:
    """`scrypt$n$r$p$salt$key`, all parameters recoverable from the value."""
    salt = secrets.token_bytes(SALT_BYTES)
    key = _derive(password, salt, N, R, P)
    return f"{PREFIX}${N}${R}${P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check. False for a malformed or missing hash, never raises."""
    if not stored:
        return False
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored.split("$")
        if scheme != PREFIX:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(key_b64)
        candidate = _derive(password, salt, int(n), int(r), int(p))
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(candidate, expected)


def needs_rehash(stored: str | None) -> bool:
    """True when a stored hash uses weaker parameters than the current ones."""
    if not stored:
        return False
    try:
        scheme, n, r, p, _, _ = stored.split("$")
    except ValueError:
        return True
    return scheme != PREFIX or (int(n), int(r), int(p)) != (N, R, P)


# A real hash of a value nobody knows, used to spend the same time on an
# unknown address as on a known one. Built at import so the cost is paid once.
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


def waste_time() -> None:
    """Spend a verification's worth of time, so timing reveals nothing."""
    verify_password("not-the-password", DUMMY_HASH)
