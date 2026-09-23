"""Request-scoped plumbing: who is viewing, what they may do, and CSRF.

`Viewer` is resolved once per request and carries everything the shell needs,
so a page no longer does its own identity lookup and the allowance shown in
the masthead is the same number the limiter enforced.
"""

from __future__ import annotations

import uuid

from dataclasses import dataclass
from typing import Any

from fastapi import Cookie, Depends, Form, Header, HTTPException, Request as Req
from markupsafe import Markup
from sqlalchemy.orm import Session

from sabi.accounts import identity as identity_mod
from sabi.accounts import sessions as sessions_mod
from sabi.accounts import tokens
from sabi.config import settings
from sabi.db import get_session
from sabi.limits import limiter
from sabi.models import AuthSession, User

ANON_COOKIE = "sabi_id"
# The longest a browser will honour.
ANON_MAX_AGE = 400 * 24 * 3600
CSRF_FIELD = "csrf_token"


class LoginRequired(Exception):
    """Raised by `require_login`.

    A FastAPI dependency cannot return a redirect, so this is turned into one
    by an exception handler on the app.
    """

    def __init__(self, next_url: str = "/") -> None:
        self.next_url = next_url


@dataclass
class Viewer:
    user: User
    anon_id: str
    session: AuthSession | None
    anon_is_new: bool
    verdict: Any
    csrf_token: str

    @property
    def is_authenticated(self) -> bool:
        return self.session is not None and bool(self.user.password_hash)

    @property
    def email(self) -> str | None:
        return self.user.email


def client_ip(request: Req) -> str | None:
    """The client address, taken from the end of the chain rather than the start.

    `X-Forwarded-For` is a list that each proxy appends to, so the leftmost
    entry is whatever the *client* sent and the rightmost is what the last
    proxy observed. Reading the leftmost is the common mistake and it was the
    one here: a request carrying `X-Forwarded-For: 1.2.3.4` arrives at the
    proxy, which appends the real address, and the header becomes
    `1.2.3.4, <real>`. Trusting the first entry means the caller picks their
    own identity.

    That matters because this value feeds the IP rate limit -- the backstop
    that stops one person using up a whole school's free questions, precisely
    because the anonymous id is resettable. A spoofable backstop is not one.

    So: the last entry, which only a proxy can have written. With no proxy in
    front, the header is absent and the socket address is used.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [p.strip() for p in forwarded.split(",") if p.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else None


def ip_hash_for(request: Req) -> str | None:
    ip = client_ip(request)
    return limiter.hash_ip(ip) if ip else None


def viewer(
    request: Req,
    s: Session = Depends(get_session),
    sabi_id: str | None = Cookie(default=None),
    sabi_session: str | None = Cookie(default=None),
) -> Viewer:
    ident = identity_mod.resolve(
        s, anon_cookie=sabi_id, session_cookie=sabi_session
    )
    verdict = limiter.check(s, ident.user, None)
    return Viewer(
        user=ident.user,
        anon_id=ident.anon_id,
        session=ident.session,
        anon_is_new=ident.anon_is_new,
        verdict=verdict,
        csrf_token=tokens.csrf_token(ident.csrf_secret),
    )


def require_login(v: Viewer = Depends(viewer)) -> Viewer:
    if not v.is_authenticated:
        raise LoginRequired()
    return v


def require_csrf(
    request: Req,
    # Form(), not a bare default: a plain `str = ""` is read by FastAPI as a
    # *query* parameter, so the hidden field never arrives and every POST is
    # rejected as stale.
    csrf_token: str = Form(""),
    v: Viewer = Depends(viewer),
) -> Viewer:
    """Reject a POST whose token does not match this viewer's.

    `samesite="lax"` on its own is not enough once a POST carries real
    authority: Chrome's Lax+POST grace window will send a freshly minted
    cookie on a cross-site POST for about two minutes after it is set.
    """
    secret = v.session.csrf_secret if v.session else v.anon_id
    if not tokens.csrf_ok(secret, csrf_token):
        raise HTTPException(status_code=400, detail="stale form; reload and try again")
    return v


def require_login_csrf(
    request: Req,
    csrf_token: str = Form(""),
    v: Viewer = Depends(viewer),
) -> Viewer:
    """Signed in AND carrying a valid token. For authenticated POSTs.

    `require_login` alone is not enough on a state-changing route, and the
    difference is easy to miss because the form looks right either way: the
    hidden field is rendered, it is submitted, and nothing checks it. Four
    routes shipped like that -- saving and removing notebook entries, setting
    an exam date, signing out everywhere -- so a page on another site could
    have made a signed-in student delete their own revision notes.

    `tests/test_assets.py` now enumerates every POST route and asserts it
    depends on something that verifies the token, so this cannot be
    reintroduced by adding a route and forgetting.
    """
    if not v.is_authenticated:
        raise LoginRequired()
    secret = v.session.csrf_secret if v.session else v.anon_id
    if not tokens.csrf_ok(secret, csrf_token):
        raise HTTPException(status_code=400, detail="stale form; reload and try again")
    return v


# Every dependency that verifies a CSRF token. The test that enumerates POST
# routes checks each one against this, so a new guard has to be added here to
# count -- which is the point.
CSRF_GUARDS = ("require_csrf", "require_login_csrf", "require_admin")


def csrf_input(v: Viewer) -> Markup:
    """The hidden field, ready to drop into a form.

    Rendered as the first child of every form so that no opening `<form>` tag
    has to change -- three tests parse those tags byte for byte.
    """
    return Markup(
        f'<input type="hidden" name="{CSRF_FIELD}" value="{v.csrf_token}">'
    )


def base_context(request: Req, v: Viewer, nav: str = "") -> dict[str, Any]:
    """Everything `base.html` needs. Pure: no database work of its own."""
    return {
        "request": request,
        "viewer": v,
        "nav": nav,
        "csrf_input": csrf_input(v),
        "remaining": v.verdict.remaining,
        "cap": v.verdict.cap,
        "reset_phrase": v.verdict.reset_phrase,
    }


def set_anon_cookie(response: Any, anon_id: str) -> None:
    response.set_cookie(
        ANON_COOKIE,
        tokens.sign(anon_id),
        max_age=ANON_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings().environment == "production",
    )


def set_session_cookie(response: Any, token: str) -> None:
    response.set_cookie(
        sessions_mod.COOKIE,
        token,
        max_age=settings().session_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings().environment == "production",
    )


def clear_session_cookie(response: Any) -> None:
    response.delete_cookie(sessions_mod.COOKIE, samesite="lax")


def rotate_anon_cookie(response: Any) -> str:
    """Give this device a brand new anonymous identity.

    Signing up claims the anonymous row rather than creating a second one, so
    that the questions asked before signing up follow the student in. The
    consequence, which was not handled: after logging out, the device's
    `sabi_id` still pointed at that same row, which now belongs to an account.

    On a shared phone -- a sibling, a cybercafe, the normal case for this
    audience -- the next person to pick it up was anonymous but *was the
    previous student's user row*. They inherited that account's daily
    allowance, their questions were written against that account's history,
    and `/auth/viewer` handed them the account's email address.

    So logging out mints a fresh anonymous id. Logging out means this device is
    no longer that person, which is what a student pressing the button
    believes it means.
    """
    anon_id = uuid.uuid4().hex
    set_anon_cookie(response, anon_id)
    return anon_id


def finish(response: Any, v: Viewer) -> Any:
    """Set the anonymous cookie if this request minted one."""
    if v.anon_is_new:
        set_anon_cookie(response, v.anon_id)
    return response


def require_admin(x_admin_token: str | None = Header(default=None)) -> bool:
    """Unchanged from before accounts existed, and deliberately so.

    A header token with no login form, returning 404 on both the unconfigured
    and the wrong-token path, so the admin surface is indistinguishable from
    one that does not exist. That pattern is right for admin and wrong for
    students: a login page has to exist and has to say "wrong password".
    """
    import secrets as _secrets

    token = settings().admin_token
    if not token:
        raise HTTPException(status_code=404)
    if not x_admin_token or not _secrets.compare_digest(x_admin_token, token):
        raise HTTPException(status_code=404)
    return True
