"""The web app.

Server-rendered HTML. The composer is a real form POST and the source panels are
`<details>` elements, so the whole thing works with JavaScript off -- which
matters when the audience is on cheap Android handsets over patchy mobile data.
JavaScript only upgrades: it keeps you on the page, shows a visible working
state, and turns a timeout into an explanation instead of a spinner.
"""

from __future__ import annotations

import secrets
import uuid
from pathlib import Path
from typing import Any

from fastapi import Cookie, Depends, FastAPI, Form, Header, HTTPException, Request as Req
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from sabi.answer.service import answer_question
from sabi.api.render import anchor_id, attribution_label, render_answer, render_source
from sabi.config import runtime, settings
from sabi.db import get_session
from sabi.limits import limiter
from sabi.models import Feedback, GoldenItem, Request as RequestRow, User, WaitlistEntry

BASE_DIR = Path(__file__).resolve().parent
COOKIE = "sabi_id"
COOKIE_MAX_AGE = 400 * 24 * 3600  # the longest a browser will honour

app = FastAPI(title="Sabi", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["anchor_id"] = anchor_id
templates.env.globals["attribution_label"] = attribution_label
templates.env.filters["render_answer"] = render_answer
templates.env.filters["render_source"] = render_source

EXAMPLES = [
    "Find the sum of the interior angles of a polygon with 12 sides",
    "The 5th term of an AP is 11 and the 9th is 23. Find the common difference.",
    "A bag has 5 red, 3 blue and 2 green balls. What is P(both red) without replacement?",
    "Simplify 27^(2/3) x 16^(-1/2)",
]


def client_ip(request: Req) -> str | None:
    """Real client address behind a proxy, if the proxy told us."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def anon_id_from(cookie_value: str | None) -> tuple[str, bool]:
    """Return (anon_id, is_new). Device-scoped, opaque, no PII."""
    if cookie_value and 16 <= len(cookie_value) <= 64 and cookie_value.isalnum():
        return cookie_value, False
    return uuid.uuid4().hex, True


def set_cookie(response: Any, anon_id: str) -> None:
    response.set_cookie(
        COOKIE,
        anon_id,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings().environment == "production",
    )


def base_context(request: Req, s: Session, anon_id: str) -> dict[str, Any]:
    user = limiter.get_or_create_user(s, anon_id)
    verdict = limiter.check(s, user, None)
    return {
        "request": request,
        "remaining": verdict.remaining,
        "cap": verdict.cap,
        "reset_phrase": verdict.reset_phrase,
    }


@app.get("/healthz")
def healthz() -> JSONResponse:
    from sabi.db import ping

    return JSONResponse({"ok": ping()})


@app.get("/", response_class=HTMLResponse)
def index(
    request: Req,
    s: Session = Depends(get_session),
    sabi_id: str | None = Cookie(default=None),
):
    anon_id, is_new = anon_id_from(sabi_id)
    ctx = base_context(request, s, anon_id)
    ctx["examples"] = EXAMPLES
    response = templates.TemplateResponse(request, "index.html", ctx)
    if is_new:
        set_cookie(response, anon_id)
    return response


@app.post("/ask", response_class=HTMLResponse)
def ask(
    request: Req,
    question: str = Form(""),
    s: Session = Depends(get_session),
    sabi_id: str | None = Cookie(default=None),
):
    anon_id, is_new = anon_id_from(sabi_id)
    result = answer_question(
        question=question,
        anon_id=anon_id,
        ip=client_ip(request),
        client="web",
    )

    known = {c.locator for c in result.citations}
    ctx = {
        "request": request,
        "result": result,
        "known_locators": known,
        "remaining": result.remaining_today,
        "cap": result.daily_cap,
        "reset_phrase": result.reset_phrase,
        "examples": EXAMPLES,
    }
    template = "capped.html" if result.capped else "answer.html"
    response = templates.TemplateResponse(request, template, ctx)
    if is_new:
        set_cookie(response, anon_id)
    return response


@app.post("/feedback")
def feedback(
    request: Req,
    request_id: str = Form(...),
    vote: int = Form(...),
    reason: str = Form(""),
    s: Session = Depends(get_session),
    sabi_id: str | None = Cookie(default=None),
):
    """Store a vote against the request it belongs to.

    Nothing identifying is stored: the feedback row carries the anonymous user
    id and a snapshot of what produced the answer, and nothing else.
    """
    anon_id, _ = anon_id_from(sabi_id)
    try:
        rid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="bad request id")

    row = s.get(RequestRow, rid)
    if row is None:
        raise HTTPException(status_code=404, detail="unknown request")

    user = limiter.get_or_create_user(s, anon_id)
    if row.user_id != user.id:
        # Votes are only accepted from the device that asked. Without this,
        # anyone could poison the review queue by posting request ids.
        raise HTTPException(status_code=403, detail="not your request")

    existing = s.execute(
        select(Feedback).where(Feedback.request_id == rid, Feedback.user_id == user.id)
    ).scalar_one_or_none()

    snapshot = {
        "question": row.question,
        "answer": row.answer,
        "retrieved_refs": row.retrieved_refs,
        "cited_refs": row.cited_refs,
        "model": row.model,
        "prompt_version": row.prompt_version,
        "retrieval_confidence": row.retrieval_confidence,
        "refused": row.refused,
        "refusal_kind": row.refusal_kind,
        "route": row.route,
    }

    if existing:
        existing.vote = int(vote)
        existing.reason = reason or None
        existing.snapshot = snapshot
    else:
        s.add(
            Feedback(
                request_id=rid,
                user_id=user.id,
                vote=1 if int(vote) > 0 else -1,
                reason=reason or None,
                snapshot=snapshot,
            )
        )

    accepts_html = "text/html" in (request.headers.get("accept") or "")
    if accepts_html:
        return RedirectResponse(f"/thanks?vote={1 if int(vote) > 0 else -1}", status_code=303)
    return JSONResponse({"ok": True})


@app.get("/thanks", response_class=HTMLResponse)
def thanks(request: Req, vote: int = 1, s: Session = Depends(get_session),
           sabi_id: str | None = Cookie(default=None)):
    anon_id, _ = anon_id_from(sabi_id)
    ctx = base_context(request, s, anon_id)
    ctx["vote"] = vote
    return templates.TemplateResponse(request, "thanks.html", ctx)


@app.get("/waitlist", response_class=HTMLResponse)
def waitlist_form(request: Req, s: Session = Depends(get_session),
                  sabi_id: str | None = Cookie(default=None)):
    anon_id, _ = anon_id_from(sabi_id)
    ctx = base_context(request, s, anon_id)
    ctx["saved"] = False
    return templates.TemplateResponse(request, "waitlist.html", ctx)


@app.post("/waitlist", response_class=HTMLResponse)
def waitlist_save(
    request: Req,
    email: str = Form(""),
    s: Session = Depends(get_session),
    sabi_id: str | None = Cookie(default=None),
):
    anon_id, _ = anon_id_from(sabi_id)
    user = limiter.get_or_create_user(s, anon_id)
    email = (email or "").strip()[:320]
    s.add(WaitlistEntry(user_id=user.id, email=email or None))
    ctx = base_context(request, s, anon_id)
    ctx["saved"] = True
    ctx["left_email"] = bool(email)
    return templates.TemplateResponse(request, "waitlist.html", ctx)


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Req, s: Session = Depends(get_session),
            sabi_id: str | None = Cookie(default=None)):
    anon_id, _ = anon_id_from(sabi_id)
    ctx = base_context(request, s, anon_id)
    cfg = runtime()
    ctx["cap"] = int(cfg.get("plans.free.daily_question_cap", 15))
    return templates.TemplateResponse(request, "privacy.html", ctx)


# --------------------------------------------------------------------- admin
# The admin surface does not exist unless SABI_ADMIN_TOKEN is set. There is no
# default credential and no login form to brute force.


def require_admin(x_admin_token: str | None = Header(default=None)) -> bool:
    token = settings().admin_token
    if not token:
        raise HTTPException(status_code=404)
    if not x_admin_token or not secrets.compare_digest(x_admin_token, token):
        raise HTTPException(status_code=404)
    return True


@app.get("/admin/review", response_class=HTMLResponse)
def review_queue(
    request: Req,
    _: bool = Depends(require_admin),
    s: Session = Depends(get_session),
):
    rows = (
        s.execute(
            select(Feedback)
            .where(Feedback.vote < 0, Feedback.promoted_golden_id.is_(None))
            .order_by(desc(Feedback.created_at))
            .limit(50)
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request, "admin_review.html", {"request": request, "rows": rows}
    )


@app.post("/admin/review/{feedback_id}/promote")
def promote(
    feedback_id: int,
    corrected_answer: str = Form(""),
    expected_value: str = Form(""),
    answerable: str = Form("yes"),
    _: bool = Depends(require_admin),
    s: Session = Depends(get_session),
):
    """Promote a down-voted answer into the golden dataset.

    This is a data move, not a rewrite: the feedback snapshot already holds the
    question, the retrieved refs and the model, because the schemas were made
    compatible for exactly this.
    """
    fb = s.get(Feedback, feedback_id)
    if fb is None:
        raise HTTPException(status_code=404)

    snap = fb.snapshot or {}
    is_answerable = answerable == "yes"
    slug = f"fb-{fb.id:05d}"

    item = GoldenItem(
        slug=slug,
        origin="feedback",
        question=snap.get("question", ""),
        expected_answer=corrected_answer or None,
        expected_value=expected_value or None,
        expected_docs=[
            r.split("#", 1)[0] for r in (snap.get("retrieved_refs") or [])
        ][:3] if is_answerable else [],
        answerable=is_answerable,
        unanswerable_kind=None if is_answerable else "not_in_corpus",
        notes=f"promoted from feedback {fb.id}; reason={fb.reason}",
        source_feedback_id=fb.id,
    )
    s.add(item)
    s.flush()
    fb.promoted_golden_id = item.id

    return JSONResponse({"ok": True, "golden_id": item.id, "slug": slug})
