"""Request-scoped plumbing for the JSON API.

The identity, CSRF and metering machinery is the existing one from
`sabi/api/deps.py` -- none of it is reimplemented here, because two notions of
who is logged in would eventually disagree and the one that disagreed quietly
would be the security-relevant one.

What differs is only how a failure is *reported*. The Jinja surface redirects
an unauthenticated visitor to the login page; an API must answer with JSON and
a status code, because its caller is a fetch, not a browser following a 303.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request as Req
from sqlalchemy.orm import Session

from sabi.api.deps import Viewer, viewer
from sabi.api.v1.schemas import Allowance, Problem, ViewerOut
from sabi.db import get_session

# The header a browser sends with `fetch`. Checked in addition to the CSRF
# token, not instead of it: `SameSite=Lax` alone leaves Chrome's Lax+POST
# grace window open for about two minutes after a cookie is set.
CSRF_HEADER = "x-sabi-csrf"


def problem(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    """An HTTPException whose detail is a `Problem`, so every error has one shape."""
    payload = Problem(code=code, message=message, **extra).model_dump(
        exclude_none=True
    )
    return HTTPException(status_code=status, detail=payload)


def api_viewer(v: Viewer = Depends(viewer)) -> Viewer:
    """Whoever is calling. Anonymous is a legitimate answer."""
    return v


def require_account(v: Viewer = Depends(api_viewer)) -> Viewer:
    """Signed in. Answers 401 rather than redirecting."""
    if not v.is_authenticated:
        raise problem(
            401,
            "unauthenticated",
            "You need an account for this. Asking questions works without one.",
        )
    return v


def require_csrf_header(request: Req, v: Viewer = Depends(api_viewer)) -> Viewer:
    """Verify the CSRF token on a mutating request.

    The token arrives in a header rather than a form field, because the caller
    is JSON. The secret is the same one the Jinja surface uses -- the session's
    for a signed-in viewer, the signed anonymous id otherwise -- so a single
    token works across both surfaces during the migration.

    The Origin check is belt and braces on top: with the API and the web app on
    one origin there is never a legitimate cross-origin mutating request.
    """
    from sabi.accounts import tokens

    secret = v.session.csrf_secret if v.session else v.anon_id
    supplied = request.headers.get(CSRF_HEADER, "")
    if not tokens.csrf_ok(secret, supplied):
        raise problem(
            403, "forbidden", "This page has gone stale. Reload and try again."
        )

    origin = request.headers.get("origin")
    if origin:
        host = request.headers.get("host", "")
        if host and not origin.endswith(host):
            raise problem(403, "forbidden", "Cross-origin request refused.")
    return v


def require_account_csrf(
    request: Req, v: Viewer = Depends(require_csrf_header)
) -> Viewer:
    """Signed in AND carrying a valid token.

    Separate from `require_csrf_header` for the same reason the Jinja surface
    keeps `require_login_csrf` separate: four routes once shipped with a login
    check and no token check, and the difference is invisible from the outside
    because the form looks right either way.
    """
    if not v.is_authenticated:
        raise problem(
            401,
            "unauthenticated",
            "You need an account for this. Asking questions works without one.",
        )
    return v


def require_consent(v: Viewer = Depends(require_account)) -> Viewer:
    """For anything a minor may not do until a guardian has confirmed.

    Practice on free content stays open while consent is pending -- the point
    is to limit what is *collected* and what is spent, not to lock a child out
    of studying while a parent finds their phone.
    """
    if consent_state(v) == "pending":
        raise problem(
            403,
            "consent_required",
            "A parent or guardian needs to confirm this account first. "
            "You can keep practising while you wait.",
        )
    return v


# ------------------------------------------------------------------ viewer


def is_minor(v: Viewer) -> bool:
    """Under 18, from a volunteered date of birth.

    Absent a date of birth this is False, which is the honest reading: we do
    not know, and guessing at a child from behavioural signals would be worse
    than asking.
    """
    dob = getattr(v.user, "date_of_birth", None)
    if not dob:
        return False
    from datetime import date

    today = date.today()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return years < 18


def consent_state(v: Viewer) -> str:
    if not is_minor(v):
        return "not_required"
    return "granted" if getattr(v.user, "guardian_consent_at", None) else "pending"


def viewer_out(s: Session, v: Viewer) -> ViewerOut:
    from sabi import vision
    from sabi.limits import limiter
    from sabi.models import StudentProfile

    plan = limiter.plan_for(s, v.user)
    profile = s.get(StudentProfile, v.user.id)

    return ViewerOut(
        authenticated=v.is_authenticated,
        csrf_token=v.csrf_token,
        # Only when signed in. Belt and braces alongside rotating the
        # anonymous id on logout: a device that somehow still carried an
        # account's row must not be told that account's email address.
        display_name=v.email if v.is_authenticated else None,
        is_minor=is_minor(v),
        consent_state=consent_state(v),
        onboarded=bool(profile and profile.completed_at),
        allowance=Allowance(
            questions_remaining=v.verdict.remaining,
            questions_cap=v.verdict.cap,
            # The tutor spends the question allowance: it is the same model
            # call. Photos and exams have their own, because they are not.
            tutor_remaining=v.verdict.remaining,
            photos_remaining=vision.ocr_remaining(s, v.user),
            exams_remaining=max(0, getattr(plan, "daily_exam_cap", 0) or 0),
            resets_phrase=v.verdict.reset_phrase,
        ),
    )


def db(s: Session = Depends(get_session)) -> Session:
    return s
