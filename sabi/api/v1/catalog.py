"""Catalog and identity: what exists, and who is asking.

The one rule worth restating at every read: `servable()` is the only predicate
that decides whether a question may be shown. Every route that reaches the
question bank goes through it, so "verified, and not dev-only" is written once
rather than remembered eight times.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from sabi.api.deps import Viewer, finish
from sabi.api.v1 import deps as api_deps
from sabi.api.v1.schemas import (
    ExamFormatOut,
    ExamSectionOut,
    SubjectOut,
    ViewerOut,
)
from sabi.content import formats
from sabi.models import Question, Subject

router = APIRouter()


def servable(stmt: Select) -> Select:
    """Narrow any question query to what a student may actually see.

    One function, used by every read, because the failure it prevents is
    silent: an unreviewed or unlicensed question renders exactly like a
    reviewed one, and a caller who forgets the condition gets no error at all.
    """
    return stmt.where(Question.status == "verified", Question.licence != "dev_only")


@router.get("/auth/viewer", response_model=ViewerOut, tags=["auth"])
def get_viewer(
    response: Response,
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.api_viewer),
) -> ViewerOut:
    """Who is viewing, and what they may do.

    Always succeeds. An anonymous viewer is a viewer: asking questions without
    an account is the product's default, not a degraded mode.

    `finish` is what makes the CSRF token in this response usable. A first-time
    visitor has no `sabi_id`, so one is minted while answering -- and the token
    handed out here is derived from it. Without persisting that cookie the next
    request mints a *different* id, the secrets do not match, and every write
    is refused as stale. That is the entire signup flow for anyone arriving
    with a clean browser, and it is invisible until the API is actually run.
    """
    finish(response, v)
    return api_deps.viewer_out(s, v)


@router.get("/catalog/subjects", response_model=list[SubjectOut], tags=["catalog"])
def list_subjects(
    s: Session = Depends(api_deps.db),
    include_unavailable: bool = False,
) -> list[SubjectOut]:
    """Subjects, with honest availability.

    `available` is false until a subject has enough verified content. Years
    are the years that actually hold servable questions -- never padded, so a
    student choosing 2019 cannot land on an empty set.
    """
    rows = s.execute(select(Subject).order_by(Subject.name)).scalars().all()

    years = {}
    for code, year in s.execute(
        servable(select(Question.subject_code, Question.year).distinct())
    ):
        years.setdefault(code, []).append(year)

    return [
        SubjectOut(
            code=r.code,
            name=r.name,
            track=r.track,
            available=r.available,
            years_available=sorted(years.get(r.code, []), reverse=True),
        )
        for r in rows
        if r.available or include_unavailable
    ]


def format_out(fmt) -> ExamFormatOut:
    nav = fmt.data.get("navigation", {})
    return ExamFormatOut(
        key=fmt.key,
        exam_body=fmt.data["exam_body"],
        exam_name=fmt.data["exam_name"],
        delivery=fmt.data.get("delivery"),
        total_duration_minutes=fmt.data.get("total_duration_minutes"),
        option_labels=fmt.option_labels,
        sections=[
            ExamSectionOut(
                key=sec["key"],
                title=sec["title"],
                subject=sec.get("subject"),
                question_count=sec["question_count"],
                question_type=sec["question_type"],
                compulsory=sec.get("compulsory", False),
            )
            for sec in fmt.data["sections"]
        ],
        scale_max=fmt.data.get("scoring", {}).get("scale_max"),
        keyboard=nav.get("keyboard", {}),
        show_attempted_count_on_submit=nav.get(
            "show_attempted_count_on_submit", True
        ),
        verified_on=fmt.data["verified_on"],
        source_url=fmt.data["source_url"],
    )


@router.get("/catalog/exams", response_model=list[ExamFormatOut], tags=["catalog"])
def list_exams() -> list[ExamFormatOut]:
    """Every exam format, including the key bindings its simulator needs.

    The keyboard map is sent rather than compiled in, so the client hard-codes
    nothing: JAMB's bindings came from JAMB's own manual and another body's
    will differ.
    """
    return [format_out(f) for f in formats.load_all().values()]


@router.get("/catalog/topics/{subject_code}", tags=["catalog"])
def list_topics(
    subject_code: str,
    s: Session = Depends(api_deps.db),
) -> list[dict]:
    """Topics with servable questions, and how many each has.

    The count is shown because a topic with four questions is not a topic a
    student should be offered a set of ten from.
    """
    rows = s.execute(
        servable(
            select(Question.topic, func.count())
            .where(Question.subject_code == subject_code, Question.topic.is_not(None))
            .group_by(Question.topic)
            .order_by(Question.topic)
        )
    ).all()
    return [{"topic": r[0], "count": int(r[1])} for r in rows]
