"""Slow down repeated login failures.

The existing limiter counts questions and knows nothing about logins, so
without this there is no limit on password guessing at all. It is also a
resource control: each verification holds 16 MiB and a worker for about
100 ms, so unlimited attempts are a way to exhaust a small machine.

Both keys are hashed, matching how IPs are handled elsewhere -- a table of
failed logins should not double as a list of which addresses have accounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from sabi.accounts.tokens import salted_hash
from sabi.config import settings
from sabi.models import LoginAttempt

WINDOW = timedelta(minutes=15)
MAX_PER_EMAIL = 5
MAX_PER_IP = 20
# There is no scheduler in this project, so rows are cleared opportunistically
# on the way past. The alternative is a table that grows forever.
KEEP_FOR = timedelta(hours=24)


@dataclass
class Verdict:
    allowed: bool
    reason: str = ""


def email_key(email: str) -> str:
    return salted_hash(email.strip().lower(), settings().ip_hash_salt)


def _count(s: Session, column, value: str) -> int:
    if not value:
        return 0
    since = datetime.now(timezone.utc) - WINDOW
    return int(
        s.execute(
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                column == value,
                LoginAttempt.created_at >= since,
                LoginAttempt.ok.is_(False),
            )
        ).scalar_one()
    )


def check(s: Session, email: str, ip_hash: str | None) -> Verdict:
    if _count(s, LoginAttempt.email_hash, email_key(email)) >= MAX_PER_EMAIL:
        return Verdict(False, "too_many_for_email")
    if ip_hash and _count(s, LoginAttempt.ip_hash, ip_hash) >= MAX_PER_IP:
        return Verdict(False, "too_many_for_ip")
    return Verdict(True)


def record(s: Session, email: str, ip_hash: str | None, ok: bool) -> None:
    s.add(
        LoginAttempt(email_hash=email_key(email), ip_hash=ip_hash, ok=ok)
    )
    # Cheap and bounded: one delete of old rows per login attempt.
    s.execute(
        delete(LoginAttempt).where(
            LoginAttempt.created_at < datetime.now(timezone.utc) - KEEP_FOR
        )
    )
