"""The web app.

Server-rendered HTML. The composer is a real form POST, the source panels are
`<details>`, the FAQ is `<details>`, and log in and sign up are two real forms
on one page -- so the whole thing works with JavaScript off, which matters when
the audience is on cheap Android handsets over patchy mobile data. JavaScript
only upgrades: it keeps you on the page, shows a visible working state, turns a
timeout into an explanation instead of a spinner, and animates the swap between
the two auth panels.

Identity is resolved in exactly one place (`sabi.accounts.identity.resolve`, via
`Depends(viewer)`), so the allowance in the masthead is the same number the
limiter enforced.
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request as Req
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from sabi.accounts import recovery, sessions as sessions_mod, service
from sabi.api.deps import (
    LoginRequired,
    Viewer,
    base_context,
    clear_session_cookie,
    client_ip,
    csrf_input,
    finish,
    ip_hash_for,
    require_admin,
    require_csrf,
    require_login,
    set_session_cookie,
    viewer,
)
from sabi.api.render import anchor_id, attribution_label, render_answer, render_source
from sabi.answer.service import answer_question
from sabi.config import runtime
from sabi.db import get_session
from sabi.limits import limiter
from sabi.models import Feedback, GoldenItem, Request as RequestRow, WaitlistEntry
from sabi import notebook
from sabi.obs import dashboard as dash
from sabi.retrieval.scope import RetrievalScope, live_scopes

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Sabi", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["anchor_id"] = anchor_id
templates.env.globals["attribution_label"] = attribution_label
templates.env.globals["relative_day"] = dash.relative_day
templates.env.globals["exam_phrase"] = dash.exam_phrase
templates.env.filters["render_answer"] = render_answer
templates.env.filters["render_source"] = render_source

EXAMPLES = [
    "Find the sum of the interior angles of a polygon with 12 sides",
    "The 5th term of an AP is 11 and the 9th is 23. Find the common difference.",
    "A bag has 5 red, 3 blue and 2 green balls. What is P(both red) without replacement?",
    "Simplify 27^(2/3) x 16^(-1/2)",
]


@app.exception_handler(LoginRequired)
def login_required_handler(request: Req, exc: LoginRequired):
    """A dependency cannot return a redirect, so it raises and this converts."""
    target = request.url.path or "/"
    return RedirectResponse(f"/login?next={target}", status_code=303)


@app.get("/healthz")
def healthz() -> JSONResponse:
    from sabi.db import ping

    return JSONResponse({"ok": ping()})


# ------------------------------------------------------------------- public


@app.get("/", response_class=HTMLResponse)
def landing(request: Req):
    """The landing page.

    Deliberately touches no database and sets no cookie. It is a public page,
    and resolving an identity here would mint a `users` row for every crawler
    that ever loaded the site. An identity is created when somebody asks
    something.
    """
    return templates.TemplateResponse(
        request,
        "landing.html",
        {"request": request, "nav": "", "viewer": None, "csrf_input": ""},
    )


@app.get("/app", response_class=HTMLResponse)
def study(request: Req, v: Viewer = Depends(viewer)):
    """The study surface. Usable without an account, which is the point."""
    ctx = base_context(request, v, nav="app")
    ctx["examples"] = EXAMPLES
    # The picker only appears once there is a choice to make. With one
    # syllabus configured, a select with a single option is furniture.
    ctx["scopes"] = live_scopes()
    ctx["scope"] = RetrievalScope.safe_parse(
        request.query_params.get("subject"), request.query_params.get("exam_board")
    )
    return finish(templates.TemplateResponse(request, "index.html", ctx), v)


@app.post("/ask", response_class=HTMLResponse)
def ask(
    request: Req,
    question: str = Form(""),
    subject: str = Form(""),
    exam_board: str = Form(""),
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_csrf),
):
    # `answer_question` opens its own session, so this one has to let go of
    # its locks first. Resolving the viewer can write `last_seen_at`, and
    # holding that row lock while a second connection tries to take it is a
    # deadlock that blocks until one side times out.
    s.commit()

    # `user.anon_id` rather than the cookie value: signing up claims the
    # identity row rather than creating a new one, so this is stable across
    # devices for a logged-in student and is the single metering key.
    # The syllabus comes from the form. `safe_parse` inside the service falls
    # back to the default rather than raising, so a stale bookmark carrying a
    # subject that has since been retired gets an answer, not a 500.
    result = answer_question(
        question=question,
        anon_id=v.user.anon_id,
        # Raw address: `answer_question` salts and hashes it itself, and a raw
        # one is never stored.
        ip=client_ip(request),
        client="web",
        subject=subject or None,
        exam_board=exam_board or None,
    )
    chosen = RetrievalScope.safe_parse(subject or None, exam_board or None)

    known = {c.locator for c in result.citations}
    ctx = {
        "request": request,
        "viewer": v,
        "nav": "app",
        "csrf_input": csrf_input(v),
        "result": result,
        "known_locators": known,
        "remaining": result.remaining_today,
        "cap": result.daily_cap,
        "reset_phrase": result.reset_phrase,
        "examples": EXAMPLES,
        "scopes": live_scopes(),
        "scope": chosen,
    }
    template = "capped.html" if result.capped else "answer.html"
    return finish(templates.TemplateResponse(request, template, ctx), v)


@app.post("/feedback")
def feedback(
    request: Req,
    request_id: str = Form(...),
    vote: int = Form(...),
    reason: str = Form(""),
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_csrf),
):
    """Store a vote against the request it belongs to.

    Nothing identifying is stored: the row carries the identity id and a
    snapshot of what produced the answer, and nothing else.
    """
    try:
        rid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="bad request id")

    row = s.get(RequestRow, rid)
    if row is None:
        raise HTTPException(status_code=404, detail="unknown request")

    if row.user_id != v.user.id:
        # Votes are only accepted from whoever asked. Without this, anyone
        # could poison the review queue by posting request ids.
        raise HTTPException(status_code=403, detail="not your request")

    existing = s.execute(
        select(Feedback).where(
            Feedback.request_id == rid, Feedback.user_id == v.user.id
        )
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
        "subject": row.subject,
        "exam_board": row.exam_board,
    }

    if existing:
        existing.vote = int(vote)
        existing.reason = reason or None
        existing.snapshot = snapshot
    else:
        s.add(
            Feedback(
                request_id=rid,
                user_id=v.user.id,
                vote=1 if int(vote) > 0 else -1,
                reason=reason or None,
                snapshot=snapshot,
            )
        )

    accepts_html = "text/html" in (request.headers.get("accept") or "")
    if accepts_html:
        return RedirectResponse(
            f"/thanks?vote={1 if int(vote) > 0 else -1}", status_code=303
        )
    return JSONResponse({"ok": True})


@app.get("/thanks", response_class=HTMLResponse)
def thanks(request: Req, vote: int = 1, v: Viewer = Depends(viewer)):
    ctx = base_context(request, v)
    ctx["vote"] = vote
    return finish(templates.TemplateResponse(request, "thanks.html", ctx), v)


@app.get("/waitlist", response_class=HTMLResponse)
def waitlist_form(request: Req, v: Viewer = Depends(viewer)):
    ctx = base_context(request, v)
    ctx["saved"] = False
    return finish(templates.TemplateResponse(request, "waitlist.html", ctx), v)


@app.post("/waitlist", response_class=HTMLResponse)
def waitlist_save(
    request: Req,
    email: str = Form(""),
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_csrf),
):
    email = (email or "").strip()[:320]
    s.add(WaitlistEntry(user_id=v.user.id, email=email or None))
    ctx = base_context(request, v)
    ctx["saved"] = True
    ctx["left_email"] = bool(email)
    return finish(templates.TemplateResponse(request, "waitlist.html", ctx), v)


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Req, v: Viewer = Depends(viewer)):
    ctx = base_context(request, v, nav="privacy")
    cfg = runtime()
    ctx["free_cap"] = int(cfg.get("plans.free.daily_question_cap", 15))
    ctx["account_cap"] = int(cfg.get("plans.free_account.daily_question_cap", 25))
    return finish(templates.TemplateResponse(request, "privacy.html", ctx), v)


# --------------------------------------------------------------------- auth


def _auth_page(
    request: Req,
    v: Viewer,
    *,
    panel: str,
    error: str = "",
    field: str = "",
    email: str = "",
    next_url: str = "",
    status: int = 200,
):
    ctx = base_context(request, v, nav=panel)
    ctx.update(
        {
            "panel": panel,
            "error": error,
            "error_field": field,
            "email": email,
            "next_url": next_url,
            "min_password": service.MIN_PASSWORD,
        }
    )
    response = templates.TemplateResponse(
        request, "auth.html", ctx, status_code=status
    )
    return finish(response, v)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Req, next: str = "", v: Viewer = Depends(viewer)):
    if v.is_authenticated:
        return RedirectResponse("/dashboard", status_code=303)
    return _auth_page(request, v, panel="login", next_url=next)


@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Req, next: str = "", v: Viewer = Depends(viewer)):
    if v.is_authenticated:
        return RedirectResponse("/dashboard", status_code=303)
    return _auth_page(request, v, panel="signup", next_url=next)


@app.post("/signup", response_class=HTMLResponse)
def signup(
    request: Req,
    email: str = Form(""),
    password: str = Form(""),
    next: str = Form(""),
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_csrf),
):
    result = service.sign_up(
        s,
        user=v.user,
        email=email,
        password=password,
        ip_hash=ip_hash_for(request),
        user_agent=request.headers.get("user-agent"),
    )
    if not result.ok:
        return _auth_page(
            request,
            v,
            panel="signup",
            error=result.error,
            field=result.field_name,
            email=email,
            next_url=next,
            status=400,
        )

    # The codes exist in the clear exactly once, here. Rendered rather than
    # redirected to, because a redirect would lose them.
    ctx = base_context(request, v, nav="dashboard")
    ctx.update({"codes": result.recovery_codes, "next_url": next or "/dashboard"})
    response = templates.TemplateResponse(request, "signed_up.html", ctx)
    set_session_cookie(response, result.token or "")
    return finish(response, v)


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Req,
    email: str = Form(""),
    password: str = Form(""),
    next: str = Form(""),
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_csrf),
):
    result = service.log_in(
        s,
        email=email,
        password=password,
        ip_hash=ip_hash_for(request),
        user_agent=request.headers.get("user-agent"),
    )
    if not result.ok:
        return _auth_page(
            request,
            v,
            panel="login",
            error=result.error,
            field=result.field_name,
            email=email,
            next_url=next,
            status=400,
        )

    target = next if next.startswith("/") else "/dashboard"
    response = RedirectResponse(target, status_code=303)
    set_session_cookie(response, result.token or "")
    return response


@app.post("/logout")
def logout(
    request: Req,
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_csrf),
):
    service.log_out(s, v.session)
    response = RedirectResponse("/", status_code=303)
    clear_session_cookie(response)
    return response


# ----------------------------------------------------------------- notebook


@app.post("/notebook/save")
def notebook_save(
    request: Req,
    request_id: str = Form(...),
    note: str = Form(""),
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_login),
):
    """Keep an answer.

    Requires an account, because a notebook that vanishes when a student
    clears their browser is worse than no notebook -- they would have
    trusted it with revision they then lose.
    """
    try:
        rid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="bad request id")

    row = s.get(RequestRow, rid)
    if row is None:
        raise HTTPException(status_code=404, detail="unknown request")
    if row.user_id != v.user.id:
        # Same rule as feedback: you can only keep your own answers.
        raise HTTPException(status_code=403, detail="not your answer")

    # Rebuilt from the stored request rather than re-answered, so saving
    # costs nothing and cannot produce different text from what was shown.
    saved = notebook.save_from_request(s, user=v.user, request=row, note=note)
    return RedirectResponse(
        f"/notebook?saved={saved.id}", status_code=303
    )


@app.get("/notebook", response_class=HTMLResponse)
def notebook_page(
    request: Req,
    subject: str = "",
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_login),
):
    ctx = base_context(request, v, nav="notebook")
    ctx.update(
        {
            "entries": notebook.listing(s, user=v.user, subject=subject or None),
            "subject_counts": notebook.subjects(s, user=v.user),
            "chosen": subject,
            "total": notebook.count(s, user=v.user),
            "today": limiter.wat_today(),
            "saved": request.query_params.get("saved", ""),
        }
    )
    return templates.TemplateResponse(request, "notebook.html", ctx)


@app.post("/notebook/{entry_id}/remove")
def notebook_remove(
    request: Req,
    entry_id: int,
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_login),
):
    notebook.remove(s, user=v.user, entry_id=entry_id)
    return RedirectResponse("/notebook?saved=removed", status_code=303)


# ---------------------------------------------------------------- dashboard


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Req,
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_login),
):
    ctx = base_context(request, v, nav="dashboard")
    ctx.update(
        {
            "summary": dash.summary(s, v.user),
            "topics": dash.topics(s, v.user),
            "recent": dash.recent(s, v.user),
            "today": limiter.wat_today(),
            "codes_left": recovery.remaining(s, v.user.id),
            "devices": len(sessions_mod.active_for(s, v.user.id)),
            "saved": request.query_params.get("saved", ""),
        }
    )
    return templates.TemplateResponse(request, "dashboard.html", ctx)


@app.post("/dashboard/exam-date")
def set_exam_date(
    request: Req,
    exam_date: str = Form(""),
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_login),
):
    """The countdown. Volunteered, and clearable -- so it can be removed too."""
    raw = (exam_date or "").strip()
    if not raw:
        v.user.exam_date = None
    else:
        try:
            v.user.exam_date = date.fromisoformat(raw)
        except ValueError:
            return RedirectResponse("/dashboard?saved=bad-date", status_code=303)
    return RedirectResponse("/dashboard?saved=exam-date", status_code=303)


@app.post("/dashboard/logout-everywhere")
def logout_everywhere(
    request: Req,
    s: Session = Depends(get_session),
    v: Viewer = Depends(require_login),
):
    sessions_mod.revoke_all(s, v.user.id, keep=v.session)
    return RedirectResponse("/dashboard?saved=logged-out", status_code=303)


# --------------------------------------------------------------------- admin
# The admin surface does not exist unless SABI_ADMIN_TOKEN is set. There is no
# default credential and no login form to brute force. `require_admin` lives
# in deps.py now but is unchanged, including returning 404 rather than 403.


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
        request,
        "admin_review.html",
        {"request": request, "rows": rows, "nav": "", "viewer": None,
         "csrf_input": ""},
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

    A data move, not a rewrite: the feedback snapshot already holds the
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
        # Carried across so a promoted item stays in the slice it came from
        # rather than silently joining the Mathematics set.
        subject=snap.get("subject") or "Mathematics",
        exam_board=snap.get("exam_board") or "WAEC",
    )
    s.add(item)
    s.flush()
    fb.promoted_golden_id = item.id

    return JSONResponse({"ok": True, "golden_id": item.id, "slug": slug})
