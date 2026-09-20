"""Signup, login, logout, and folding one identity into another.

The important decision is in `sign_up`: it does not create a user. It sets
credentials on the identity the device already has, so every `requests`,
`usage_events` and `feedback` row keeps pointing at the same `users.id`. The
questions somebody asked before signing up are simply already theirs, with no
backfill and no migration -- and the daily allowance cannot be reset by
signing up, because `usage_today` keys on that same id.

What signing up *does* change is the plan, which is a row in `plans` rather
than a schema change, so the reward for making an account is a higher cap
rather than a fresh one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from sabi.accounts import passwords, recovery, sessions, throttle
from sabi.models import (
    AuthSession,
    Feedback,
    Plan,
    Request as RequestRow,
    UsageEvent,
    User,
    WaitlistEntry,
)

# The plan an account gets. A row, not a migration -- see config/limits.yaml.
ACCOUNT_PLAN = "free_account"

MIN_PASSWORD = 10
# Deliberately permissive: the job is to catch a typo, not to adjudicate what
# a valid address is. Nothing is sent to it, so a wrong one costs only the
# student's own recovery route.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$")


@dataclass
class AuthResult:
    ok: bool
    user: User | None = None
    session: AuthSession | None = None
    token: str | None = None
    error: str = ""
    # Which form field the error belongs to. Not named `field`: that would
    # shadow `dataclasses.field` in this class body and turn the line below
    # into a call on a string.
    field_name: str = ""
    recovery_codes: list[str] = field(default_factory=list)


def normalise_email(email: str) -> str:
    return email.strip().lower()


def find_by_email(s: Session, email: str) -> User | None:
    """A live account for this address. Merged-away rows are not accounts."""
    return s.execute(
        select(User).where(
            User.email_normalised == normalise_email(email),
            User.merged_into_user_id.is_(None),
        )
    ).scalar_one_or_none()


def _password_problem(password: str) -> str:
    if len(password) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters. Longer is better than odder."
    if password.strip() == "":
        return "That is only spaces."
    return ""


def sign_up(
    s: Session,
    *,
    user: User,
    email: str,
    password: str,
    ip_hash: str | None = None,
    user_agent: str | None = None,
) -> AuthResult:
    """Turn the identity in `user` into an account. No new row is created."""
    email = email.strip()
    if not EMAIL_RE.match(email):
        return AuthResult(False, error="That does not look like an email address.", field_name="email")

    problem = _password_problem(password)
    if problem:
        return AuthResult(False, error=problem, field_name="password")

    if user.password_hash:
        return AuthResult(
            False,
            error="You are already signed in on this device.",
            field_name="email",
        )

    # Signing up was the one unthrottled path that costs real work. Each
    # attempt hashes a password, which holds 16 MiB and a worker for about
    # 100ms, so an unthrottled endpoint is both an account-spam vector and a
    # way to exhaust a small machine. The IP limit is what bites here, since
    # an attacker picks a fresh address each time.
    gate = throttle.check(s, email, ip_hash)
    if not gate.allowed:
        return AuthResult(
            False,
            error="Too many attempts from here. Wait fifteen minutes and try again.",
            field_name="email",
        )

    if find_by_email(s, email) is not None:
        throttle.record(s, email, ip_hash, ok=False)
        # Says an account exists, which is unavoidable on a signup form: the
        # address either can or cannot be used, and hiding that would mean
        # taking a password for an account that will not be created.
        return AuthResult(
            False,
            error="There is already an account with that address. Log in instead.",
            field_name="email",
        )

    user.email = email
    user.email_normalised = normalise_email(email)
    user.password_hash = passwords.hash_password(password)
    user.signed_up_at = datetime.now(timezone.utc)
    if s.get(Plan, ACCOUNT_PLAN) is not None:
        user.plan = ACCOUNT_PLAN
    s.flush()

    codes = recovery.issue(s, user)
    throttle.record(s, email, ip_hash, ok=True)
    row, token = sessions.start(s, user, ip_hash=ip_hash, user_agent=user_agent)
    return AuthResult(True, user=user, session=row, token=token, recovery_codes=codes)


def log_in(
    s: Session,
    *,
    email: str,
    password: str,
    ip_hash: str | None = None,
    user_agent: str | None = None,
) -> AuthResult:
    """Check credentials and open a session.

    Deliberately does *not* merge whatever anonymous identity this device was
    carrying. That row may belong to somebody else -- a shared phone, a
    sibling, a cybercafe -- and importing a stranger's questions into your
    notebook would be a real leak. The dashboard offers the merge explicitly
    instead, defaulting to no.
    """
    email = email.strip()
    if not email or not password:
        return AuthResult(False, error="Enter your email and password.", field_name="email")

    gate = throttle.check(s, email, ip_hash)
    if not gate.allowed:
        return AuthResult(
            False,
            error=(
                "Too many attempts. Wait fifteen minutes and try again, or use "
                "one of your recovery codes."
            ),
            field_name="password",
        )

    user = find_by_email(s, email)
    if user is None or not user.password_hash:
        # Same cost as a real check, so timing does not reveal whether the
        # address has an account.
        passwords.waste_time()
        throttle.record(s, email, ip_hash, ok=False)
        return AuthResult(False, error="Wrong email or password.", field_name="password")

    if not passwords.verify_password(password, user.password_hash):
        throttle.record(s, email, ip_hash, ok=False)
        return AuthResult(False, error="Wrong email or password.", field_name="password")

    # Opportunistic upgrade: if the parameters have been raised since this hash
    # was written, rewrite it now that the password is in hand.
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(password)

    throttle.record(s, email, ip_hash, ok=True)
    user.last_seen_at = datetime.now(timezone.utc)
    row, token = sessions.start(s, user, ip_hash=ip_hash, user_agent=user_agent)
    return AuthResult(True, user=user, session=row, token=token)


def log_out(s: Session, row: AuthSession | None) -> None:
    if row is not None:
        sessions.revoke(s, row)


def change_password(
    s: Session, *, user: User, new_password: str, keep: AuthSession | None = None
) -> AuthResult:
    problem = _password_problem(new_password)
    if problem:
        return AuthResult(False, error=problem, field_name="password")
    user.password_hash = passwords.hash_password(new_password)
    # Every other session goes: a password change that leaves an attacker
    # logged in has not changed anything.
    sessions.revoke_all(s, user.id, keep=keep)
    return AuthResult(True, user=user)


def merge_user(s: Session, *, source: User, target: User) -> int:
    """Fold `source` into `target`, moving its traffic across.

    Only ever called on an explicit, confirmed request -- never on login. The
    unique index on `email_normalised` is partial on `merged_into_user_id`
    being null, so the source row releases any address it was holding.

    `feedback` is handled separately: there is a unique index on
    (request_id, user_id), and `/feedback` resolves that pair with
    `scalar_one_or_none()`, so producing two rows for one request would turn
    that route into a 500 rather than a duplicate.
    """
    if source.id == target.id:
        return 0

    moved = 0
    for model in (RequestRow, UsageEvent, WaitlistEntry):
        moved += int(
            s.execute(
                update(model)
                .where(model.user_id == source.id)
                .values(user_id=target.id)
            ).rowcount
            or 0
        )

    # Feedback: move only rows whose (request_id, target) pair is still free.
    taken = set(
        s.execute(
            select(Feedback.request_id).where(Feedback.user_id == target.id)
        ).scalars()
    )
    for row in s.execute(
        select(Feedback).where(Feedback.user_id == source.id)
    ).scalars():
        if row.request_id in taken:
            # The target already voted on this request; their own vote wins.
            s.delete(row)
        else:
            row.user_id = target.id
            taken.add(row.request_id)
            moved += 1

    sessions.revoke_all(s, source.id)
    source.merged_into_user_id = target.id
    source.email_normalised = None
    s.flush()
    return moved
