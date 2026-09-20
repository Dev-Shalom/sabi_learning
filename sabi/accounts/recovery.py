"""One-time recovery codes.

This deployment has no way to send email, so "forgot password" has no route to
anybody. Rather than ship a lock with no key, or pretend a reset link works,
signup hands over five codes and says to keep them. They are hashed exactly
the way a password is, so the database is no help to anyone reading it.

The email-sending seam is `sabi/accounts/mail.py`, deliberately unimplemented.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from sabi.accounts.passwords import hash_password, verify_password
from sabi.models import RecoveryCode, User

HOW_MANY = 5
# Unambiguous on a phone screen: no O/0, no I/1/l. A student reads these off
# a screenshot or a scrap of paper, so the alphabet matters.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
GROUPS = 3
GROUP_LEN = 4


def _one_code() -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(GROUPS * GROUP_LEN))
    return "-".join(
        body[i : i + GROUP_LEN] for i in range(0, len(body), GROUP_LEN)
    )


def normalise(code: str) -> str:
    return code.strip().upper().replace(" ", "").replace("-", "")


def issue(s: Session, user: User, how_many: int = HOW_MANY) -> list[str]:
    """Replace any existing codes and return the new ones in the clear.

    They are returned once, here, and never again -- nothing stores the plain
    text, so the signup page is the only chance to write them down.
    """
    for row in s.execute(
        select(RecoveryCode).where(RecoveryCode.user_id == user.id)
    ).scalars():
        s.delete(row)

    codes = [_one_code() for _ in range(how_many)]
    for code in codes:
        s.add(
            RecoveryCode(
                user_id=user.id, code_hash=hash_password(normalise(code))
            )
        )
    s.flush()
    return codes


def redeem(s: Session, user: User, submitted: str) -> bool:
    """Spend a code. Each one works exactly once."""
    candidate = normalise(submitted)
    if not candidate:
        return False
    rows = s.execute(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None)
        )
    ).scalars()
    for row in rows:
        if verify_password(candidate, row.code_hash):
            row.used_at = datetime.now(timezone.utc)
            return True
    return False


def remaining(s: Session, user_id) -> int:
    return len(
        list(
            s.execute(
                select(RecoveryCode.id).where(
                    RecoveryCode.user_id == user_id,
                    RecoveryCode.used_at.is_(None),
                )
            ).scalars()
        )
    )
