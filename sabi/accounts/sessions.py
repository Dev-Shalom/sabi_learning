"""Server-side sessions.

The cookie holds a random token; the database holds only its SHA-256. So a
database dump cannot be used to log in as anyone, and revoking a session is a
single UPDATE rather than a wait for an expiry to pass.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from sabi.accounts.tokens import new_session_token, sha256_hex
from sabi.config import settings
from sabi.models import AuthSession, User

COOKIE = "sabi_session"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def start(
    s: Session,
    user: User,
    ip_hash: str | None = None,
    user_agent: str | None = None,
) -> tuple[AuthSession, str]:
    """Open a session. Returns the row and the raw token for the cookie."""
    token = new_session_token()
    row = AuthSession(
        token_hash=sha256_hex(token),
        user_id=user.id,
        csrf_secret=secrets.token_urlsafe(24),
        expires_at=_now() + timedelta(days=settings().session_days),
        ip_hash=ip_hash,
        user_agent_hash=(
            hashlib.sha256(user_agent.encode("utf-8")).hexdigest()[:48]
            if user_agent
            else None
        ),
    )
    s.add(row)
    s.flush()
    return row, token


def lookup(s: Session, token: str | None) -> AuthSession | None:
    """The live session for this token, or None.

    Expiry and revocation are checked here rather than by a cleanup job,
    because there is no scheduler in this project and a session that is only
    logically expired is not expired.
    """
    if not token:
        return None
    row = s.execute(
        select(AuthSession).where(AuthSession.token_hash == sha256_hex(token))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None
    if row.expires_at <= _now():
        return None
    return row


def touch(s: Session, row: AuthSession) -> None:
    """Record use, and slide the expiry forward."""
    row.last_seen_at = _now()
    row.expires_at = _now() + timedelta(days=settings().session_days)


def revoke(s: Session, row: AuthSession) -> None:
    row.revoked_at = _now()


def revoke_all(s: Session, user_id, keep: AuthSession | None = None) -> int:
    """Log out everywhere. Used on a password change and offered on the
    dashboard, which is the only reason the session list is worth storing."""
    stmt = (
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    if keep is not None:
        stmt = stmt.where(AuthSession.id != keep.id)
    return int(s.execute(stmt).rowcount or 0)


def active_for(s: Session, user_id) -> list[AuthSession]:
    return list(
        s.execute(
            select(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > _now(),
            )
            .order_by(AuthSession.last_seen_at.desc())
        ).scalars()
    )
