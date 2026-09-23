"""The tutor, over JSON.

This is a thin envelope around `sabi.answer.service.answer_question`, and thin
is the point. The welfare guardrail, the rate limit, the budget kill switch,
the semantic cache with its numeric guard, the scoped retrieval, the refusal
check, the model routing and the citation validation all stay exactly where
they are. Reimplementing any of that for the API would create a second path
with different safety properties, and the one that diverged quietly would be
the one that mattered.

Two things this layer does add:

* **Subject is chosen, never classified.** A subject code arrives from the
  client and is resolved against the catalog. Inferring it from the question
  text would mean a misclassified question retrieves the wrong corpus and then
  *correctly* refuses, and the student cannot tell why.
* **A refusal is a 200.** Out of subject, out of study, or absent from the
  corpus is an answer, not an error. Returning 4xx would make honest refusal
  look like a fault and invite a client to retry it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from sabi.api.deps import Viewer
from sabi.api.v1 import deps as api_deps
from sabi.api.v1.schemas import CitationOut, TutorAnswerOut, TutorAskRequest
from sabi.models import Subject

router = APIRouter(prefix="/tutor", tags=["tutor"])


@router.post("/ask", response_model=TutorAnswerOut)
def ask(
    body: TutorAskRequest,
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.require_csrf_header),
) -> TutorAnswerOut:
    """Ask the tutor, within one subject."""
    from sabi.answer.service import answer_question
    from sabi.llm.base import LLMUnavailable

    subject = s.get(Subject, body.subject_code.upper())
    if subject is None:
        raise api_deps.problem(404, "not_found", "No such subject.")
    if not subject.available:
        # An honest absence rather than an empty answer. The tutor has nothing
        # to be grounded in for this subject yet, and saying so is the whole
        # product.
        raise api_deps.problem(
            503,
            "unavailable",
            f"{subject.name} is not open yet. Sabi only answers from material "
            "it actually holds, and there is not enough of it for this subject.",
        )

    try:
        result = answer_question(
            question=body.question,
            anon_id=v.anon_id,
            ip=None,
            client="api",
            plan_hint=v.verdict.plan,
            subject=subject.name,
            exam_board=body.exam_body,
        )
    except LLMUnavailable as e:
        # Visible degradation, never a silently worse answer.
        raise api_deps.problem(503, "capacity", str(e))

    if result.capped:
        # The limiter refused before any model call. The message is the
        # limiter's own, which names the cap and when it resets rather than
        # saying "try later".
        raise api_deps.problem(
            429, "rate_limited", result.text, retry_after_seconds=None
        )

    return TutorAnswerOut(
        text=result.text,
        refused=bool(result.refused),
        refusal_kind=result.refusal_kind,
        citations=[
            CitationOut(
                locator=c.locator,
                title=c.title,
                attribution=getattr(c, "attribution", None),
                text=c.text,
                highlight=getattr(c, "highlight", None),
            )
            for c in getattr(result, "citations", [])
        ],
        disclosure=getattr(result, "disclosure", ""),
        request_id=str(getattr(result, "request_id", "") or "") or None,
        confidence=getattr(result, "confidence", None),
    )
