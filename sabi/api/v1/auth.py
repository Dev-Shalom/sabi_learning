"""Signing up, logging in, logging out, over JSON.

None of the hard parts live here. Passwords, sessions, throttling and recovery
codes are `sabi/accounts/`, already built and already tested, and the Jinja
routes call exactly the same functions. This module is the translation layer
and nothing else: a second implementation of "is this password right" is how
two surfaces end up disagreeing, and the one that disagreed quietly would be
the security-relevant one.

What is genuinely different from the Jinja surface is failure. A browser
following a 303 can be sent back to a form with an error on it; a `fetch`
needs a status code and a body. That mapping is the only decision this file
makes, and it reads `AuthResult.reason` rather than the human sentence, so
improving the wording of an error cannot silently change a status code.
"""

from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter, Depends, Request as Req, Response
from sqlalchemy.orm import Session

from sabi.accounts import service
from sabi.api.deps import (
    Viewer,
    clear_session_cookie,
    finish,
    ip_hash_for,
    rotate_anon_cookie,
    set_session_cookie,
)
from sabi.api.v1.deps import db, problem, require_csrf_header, viewer_out
from sabi.api.v1.schemas import LoginIn, SignedUpOut, SignupIn, ViewerOut
from sabi.limits import limiter

router = APIRouter(tags=["auth"])

# `AuthResult.reason` -> the status code a JSON caller should see.
STATUS = {
    "bad_request": 400,
    "unauthenticated": 401,
    "conflict": 409,
    "rate_limited": 429,
}


def _refuse(s: Session, result: service.AuthResult):
    """Turn a failed AuthResult into the matching HTTP problem.

    Commits first, and that is not housekeeping. `session_scope` rolls back on
    any exception, so raising here would discard the `LoginAttempt` row that
    `service.log_in` just wrote to record the failure -- and the login throttle
    would count to one forever. The JSON surface would have had no brute-force
    protection at all, while the Jinja surface kept working, because that one
    *returns* an error page instead of raising.

    A failed attempt is a fact that happened. It outlives the request that
    failed.
    """
    s.commit()
    code = result.reason or "bad_request"
    detail = problem(STATUS.get(code, 400), code, result.error)
    if code == "rate_limited":
        # The contract promises this header on a 429. Fifteen minutes is the
        # window `sabi/accounts/throttle.py` actually uses; it is stated
        # rather than left for the caller to guess, because a client that
        # guesses will guess "retry now".
        detail.headers = {"Retry-After": "900"}
    return detail


def _now_signed_in(s: Session, v: Viewer, result: service.AuthResult) -> Viewer:
    """The viewer as it stands *after* the credentials changed.

    `v` was resolved before the request ran, so it still describes whoever was
    here a moment ago: anonymous on signup, and possibly a different person
    entirely on login, because a shared phone is the normal case here. Echoing
    it back would answer `authenticated: false` to a successful login, and
    would report the wrong person's remaining questions.

    The allowance is recomputed rather than carried over for the same reason:
    on signup the row keeps its usage and gains a larger cap, and on login the
    cap belongs to the account, not to the device.
    """
    user = result.user or v.user
    return replace(
        v,
        user=user,
        session=result.session,
        verdict=limiter.check(s, user, None),
    )


@router.post("/auth/signup", response_model=SignedUpOut, status_code=201)
def signup(
    request: Req,
    response: Response,
    body: SignupIn,
    s: Session = Depends(db),
    v: Viewer = Depends(require_csrf_header),
) -> SignedUpOut:
    """Create an account on the identity this device already has.

    No second user row: the anonymous row gains credentials. So the questions
    asked before signing up follow the student in with no backfill, and the
    daily allowance does not reset -- which is both the honest reward and what
    stops "clear the cookies and sign up again".
    """
    result = service.sign_up(
        s,
        user=v.user,
        email=body.email,
        password=body.password,
        ip_hash=ip_hash_for(request),
        user_agent=request.headers.get("user-agent"),
    )
    if not result.ok:
        raise _refuse(s, result)

    set_session_cookie(response, result.token or "")
    finish(response, v)

    # The recovery codes exist in the clear exactly once, in this response.
    # They are never stored recoverably and never sent again.
    return SignedUpOut(
        viewer=viewer_out(s, _now_signed_in(s, v, result)),
        recovery_codes=result.recovery_codes,
    )


@router.post("/auth/login", response_model=ViewerOut)
def login(
    request: Req,
    response: Response,
    body: LoginIn,
    s: Session = Depends(db),
    v: Viewer = Depends(require_csrf_header),
) -> ViewerOut:
    """Log in.

    Deliberately does not merge whatever anonymous identity this device was
    carrying: it may belong to a sibling, or to the last person on a cybercafe
    machine, and importing a stranger's questions into someone's notebook is a
    real leak. The merge is offered explicitly elsewhere, defaulting to no.
    """
    result = service.log_in(
        s,
        email=body.email,
        password=body.password,
        ip_hash=ip_hash_for(request),
        user_agent=request.headers.get("user-agent"),
    )
    if not result.ok:
        raise _refuse(s, result)

    set_session_cookie(response, result.token or "")
    return viewer_out(s, _now_signed_in(s, v, result))


@router.post("/auth/logout", status_code=204)
def logout(
    s: Session = Depends(db),
    v: Viewer = Depends(require_csrf_header),
) -> Response:
    """End this session. Succeeds whether or not there was one to end."""
    service.log_out(s, v.session)

    # Built here rather than by mutating an injected `Response`. This sets two
    # cookies, and `dict(response.headers)` silently keeps only one of two
    # `Set-Cookie` lines -- which dropped the rotation below and left the
    # device carrying the account it had just logged out of.
    out = Response(status_code=204)
    clear_session_cookie(out)
    # Not just the session: the anonymous id too. See `rotate_anon_cookie` --
    # leaving it alone means the next person on a shared phone carries on as
    # this account's anonymous row.
    rotate_anon_cookie(out)
    return out
