"""Who is making this request.

One function decides it, for every route. Before accounts there were two
places that worked it out -- the page context and, separately, inside
`answer_question` -- and they could disagree by one on the allowance. This is
the single answer.

It still goes through `limiter.get_or_create_user`, which stays the only place
a `User` row is ever created, and which carries the rule that an unknown plan
must not produce an unmetered user.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from sabi.accounts import sessions, tokens
from sabi.limits import limiter
from sabi.models import AuthSession, User

# Shape check on the anonymous id, unchanged: 16-64 alphanumeric characters.
# What is new is that the cookie is signed, so the value cannot be chosen by
# whoever is sending it. That mattered little when the row held nothing; it
# matters now that it can hold the questions asked before signing up.
MIN_ANON = 16
MAX_ANON = 64


@dataclass
class Identity:
    user: User
    anon_id: str
    session: AuthSession | None
    # True when the anonymous cookie was absent, unsigned or tampered, so the
    # caller knows to set a fresh one on the response.
    anon_is_new: bool

    @property
    def is_authenticated(self) -> bool:
        return self.session is not None and bool(self.user.password_hash)

    @property
    def csrf_secret(self) -> str:
        """What the CSRF token is derived from.

        A session's own secret when there is one, so rotating the session
        invalidates open forms; the anonymous id otherwise, because anonymous
        visitors post too -- asking a question spends an allowance and writes
        a row.
        """
        return self.session.csrf_secret if self.session else self.anon_id


def anon_id_from(cookie_value: str | None) -> tuple[str, bool]:
    """Return (anon_id, is_new) from the signed cookie value."""
    raw = tokens.unsign(cookie_value)
    if raw and MIN_ANON <= len(raw) <= MAX_ANON and raw.isalnum():
        return raw, False
    return uuid.uuid4().hex, True


def resolve(
    s: Session,
    *,
    anon_cookie: str | None,
    session_cookie: str | None,
) -> Identity:
    """The identity for this request.

    A valid session wins: the logged-in user is the user, whatever anonymous
    id the device is also carrying. With no session, the anonymous id is the
    identity, created on first use.
    """
    anon_id, anon_is_new = anon_id_from(anon_cookie)

    row = sessions.lookup(s, session_cookie)
    if row is not None:
        user = s.get(User, row.user_id)
        # A merged-away or deleted user must not keep a live session.
        if user is not None and user.merged_into_user_id is None:
            sessions.touch(s, row)
            return Identity(
                user=user, anon_id=anon_id, session=row, anon_is_new=anon_is_new
            )
        sessions.revoke(s, row)

    user = limiter.get_or_create_user(s, anon_id)
    return Identity(user=user, anon_id=anon_id, session=None, anon_is_new=anon_is_new)
