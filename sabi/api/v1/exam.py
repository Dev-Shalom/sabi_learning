"""Exam mode: a faithful timed sitting.

Four properties are enforced here and each one has a failure it exists to
prevent.

**The server owns the clock.** `seconds_remaining` is recomputed from
`started_at` and `seconds_allowed` on every response. A client that changes
the device time, pauses a tab or replays an old response changes nothing.

**Nothing is marked before submission.** `ExamAnswer.correct` stays null while
a sitting is open and no route reads the answer key until `submitted_at` is
set. Marking as you go turns a timed exam into a guessing game against the
marker, which is a different exercise from the one being simulated.

**A replayed offline queue cannot lose an answer.** Each submission carries a
`client_seq`; the server keeps the highest per question. Last-write-wins would
let a stale queued answer overwrite the one a student changed after coming
back online, and they would never know.

**A submitted sitting is closed.** No further answers, and the result is only
available once it is closed -- a result before submission would be a leak of
the marking.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sabi.api.deps import Viewer
from sabi.api.v1 import deps as api_deps
from sabi.api.v1.catalog import format_out, servable
from sabi.api.v1.schemas import (
    ExamAnswerIn,
    ExamItemOut,
    ExamResultOut,
    ExamResultSection,
    ExamSessionOut,
    ExamStartRequest,
    MarkingOut,
    QuestionOut,
)
from sabi.content import formats
from sabi.models import (
    ExamAnswer,
    ExamSession,
    ExamSessionItem,
    Question,
)

router = APIRouter(prefix="/exam", tags=["exam"])


# ------------------------------------------------------------------ helpers


def _seconds_remaining(session: ExamSession) -> int:
    if session.submitted_at:
        return 0
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    return max(0, int(session.seconds_allowed - elapsed))


def _state(session: ExamSession) -> str:
    if session.submitted_at:
        return "submitted"
    return "active" if _seconds_remaining(session) > 0 else "expired"


def _question_out(q: Question, passage: str | None = None) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        type=q.type,
        stem=q.stem,
        passage=passage,
        options=[
            {"label": o["label"], "text": o["text"]} for o in (q.options or [])
        ],
        assets=q.assets or [],
        topic=q.topic,
        source_label=_source_label(q),
    )


def _source_label(q: Question) -> str:
    parts = [q.exam_body, str(q.year)]
    if q.paper:
        parts.append(f"Paper {q.paper}")
    parts.append(f"Question {q.question_number}")
    return " · ".join(parts)


def _mark(q: Question, answer: ExamAnswer) -> bool:
    """Whether this answer is right. Called only at submission."""
    if q.type == "objective":
        return bool(
            answer.selected_label
            and answer.selected_label == (q.answer or {}).get("key")
        )
    if q.type == "numeric_entry":
        from sabi.valuematch import answers_match

        expected = (q.answer or {}).get("value")
        kind = (q.answer or {}).get("value_kind", "number")
        return bool(expected and answers_match(expected, answer.value or "", kind))
    # Theory and practical are marked by a human, never automatically.
    return False


def _session_out(s: Session, row: ExamSession, *, with_items: bool) -> ExamSessionOut:
    fmt = formats.get(row.format_key)
    total = s.execute(
        select(func.count())
        .select_from(ExamSessionItem)
        .where(ExamSessionItem.session_id == row.id)
    ).scalar_one()
    answered = s.execute(
        select(func.count())
        .select_from(ExamAnswer)
        .where(
            ExamAnswer.session_id == row.id,
            (ExamAnswer.selected_label.is_not(None)) | (ExamAnswer.value.is_not(None)),
        )
    ).scalar_one()

    items: list[ExamItemOut] = []
    if with_items:
        submitted = row.submitted_at is not None
        pairs = s.execute(
            select(ExamSessionItem, Question, ExamAnswer)
            .join(Question, Question.id == ExamSessionItem.question_id)
            .outerjoin(ExamAnswer, ExamAnswer.item_id == ExamSessionItem.id)
            .where(ExamSessionItem.session_id == row.id)
            .order_by(ExamSessionItem.position)
        ).all()
        for item, question, answer in pairs:
            marking = None
            if submitted:
                # The answer key is read here and nowhere else, and only once
                # `submitted_at` is set.
                key = (question.answer or {}).get("key")
                explanation = question.explanation or {}
                why = None
                if answer and answer.selected_label:
                    chosen = next(
                        (
                            o
                            for o in (question.options or [])
                            if o["label"] == answer.selected_label
                        ),
                        None,
                    )
                    why = (chosen or {}).get("why_wrong")
                marking = MarkingOut(
                    correct=bool(answer and answer.correct),
                    correct_label=key,
                    correct_value=(question.answer or {}).get("value"),
                    explanation=explanation.get("text"),
                    why_wrong=why if not (answer and answer.correct) else None,
                    locators=explanation.get("locators", []),
                )
            items.append(
                ExamItemOut(
                    position=item.position,
                    section_key=item.section_key,
                    question=_question_out(question),
                    selected_label=answer.selected_label if answer else None,
                    value=answer.value if answer else None,
                    flagged=bool(answer and answer.flagged),
                    marking=marking,
                )
            )

    return ExamSessionOut(
        id=str(row.id),
        format=format_out(fmt),
        seconds_remaining=_seconds_remaining(row),
        state=_state(row),
        answered_count=int(answered),
        total_count=int(total),
        started_at=row.started_at,
        submitted_at=row.submitted_at,
        score=row.score,
        scale_max=row.scale_max,
        items=items,
    )


def _owned(s: Session, session_id: str, v: Viewer) -> ExamSession:
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise api_deps.problem(404, "not_found", "No such exam session.")
    row = s.get(ExamSession, sid)
    if row is None or row.user_id != v.user.id:
        # Same answer for "does not exist" and "not yours", so an id cannot be
        # probed for existence.
        raise api_deps.problem(404, "not_found", "No such exam session.")
    return row


# ------------------------------------------------------------------- routes


@router.post("/sessions", response_model=ExamSessionOut, status_code=201)
def start_session(
    body: ExamStartRequest,
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.require_account_csrf),
) -> ExamSessionOut:
    """Start a timed sitting.

    The whole paper is drawn and stored now, so the session survives going
    offline: a student on an intermittent connection must not lose the exam
    because the next question could not be fetched.
    """
    from sabi.content.formats import FormatError
    from sabi.limits import limiter

    try:
        fmt = formats.get(body.format_key)
    except FormatError:
        raise api_deps.problem(404, "not_found", "No such exam.")

    plan = limiter.plan_for(s, v.user)
    cap = int(getattr(plan, "daily_exam_cap", 0) or 0)
    taken = s.execute(
        select(func.count())
        .select_from(ExamSession)
        .where(
            ExamSession.user_id == v.user.id,
            ExamSession.started_at >= _today_start(),
        )
    ).scalar_one()
    if taken >= cap:
        raise api_deps.problem(
            429,
            "rate_limited",
            f"You have used your {cap} timed mock{'' if cap == 1 else 's'} for "
            "today. Practice mode is still open.",
        )

    row = ExamSession(
        user_id=v.user.id,
        format_key=fmt.key,
        # A copy, so re-verifying the format next season cannot retroactively
        # change how this sitting is scored or reviewed.
        format_snapshot=fmt.data,
        seconds_allowed=int(fmt.data.get("total_duration_minutes", 120)) * 60,
    )
    s.add(row)
    s.flush()

    chosen = _draw(s, fmt, body.subject_codes)
    if not chosen:
        raise api_deps.problem(
            503,
            "unavailable",
            "There are not enough verified questions for that exam yet. "
            "Practice mode has what there is.",
        )
    for position, (section_key, question) in enumerate(chosen):
        s.add(
            ExamSessionItem(
                session_id=row.id,
                question_id=question.id,
                section_key=section_key,
                position=position,
            )
        )
    s.flush()
    return _session_out(s, row, with_items=True)


def _today_start():
    from sabi.limits import limiter

    return datetime.combine(
        limiter.wat_today(), datetime.min.time(), tzinfo=timezone.utc
    )


def _draw(s: Session, fmt, subject_codes: list[str]) -> list[tuple[str, Question]]:
    """Pick the questions for a sitting, section by section.

    Draws only servable questions, and takes what exists rather than failing
    when a section is short -- an honest 32-question section is better than no
    sitting, and the result reports what was actually asked.
    """
    rng = random.Random()
    electives = list(subject_codes)
    out: list[tuple[str, Question]] = []

    for section in fmt.data["sections"]:
        code = section.get("subject_code")
        if not code:
            if section.get("compulsory") and section.get("subject"):
                code = _code_for(s, section["subject"])
            elif electives:
                code = electives.pop(0)
        if not code:
            continue

        pool = s.execute(
            servable(select(Question).where(Question.subject_code == code))
            .order_by(func.random())
            .limit(section["question_count"])
        ).scalars().all()
        rng.shuffle(pool)
        out.extend((section["key"], q) for q in pool)

    return out


def _code_for(s: Session, subject_name: str) -> str | None:
    from sabi.models import Subject

    return s.execute(
        select(Subject.code).where(Subject.name == subject_name)
    ).scalar_one_or_none()


@router.get("/sessions/{session_id}", response_model=ExamSessionOut)
def get_session(
    session_id: str,
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.require_account),
) -> ExamSessionOut:
    return _session_out(s, _owned(s, session_id, v), with_items=True)


@router.post("/sessions/{session_id}/answers", response_model=ExamSessionOut)
def save_answers(
    session_id: str,
    body: list[ExamAnswerIn],
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.require_account_csrf),
) -> ExamSessionOut:
    """Autosave, including a queue replayed after being offline.

    Accepts a batch so a client that has been offline flushes in one request.
    Returns no marking: an exam is not marked before submission.
    """
    row = _owned(s, session_id, v)
    if row.submitted_at is not None:
        raise api_deps.problem(
            409, "conflict", "That exam has been submitted. It cannot be changed."
        )
    if _seconds_remaining(row) <= 0:
        raise api_deps.problem(
            409, "conflict", "Time is up for that exam. Submit it to see your result."
        )

    items = {
        i.question_id: i
        for i in s.execute(
            select(ExamSessionItem).where(ExamSessionItem.session_id == row.id)
        ).scalars()
    }
    existing = {
        a.item_id: a
        for a in s.execute(
            select(ExamAnswer).where(ExamAnswer.session_id == row.id)
        ).scalars()
    }

    for incoming in body:
        item = items.get(incoming.question_id)
        if item is None:
            # A question that is not in this sitting is ignored rather than
            # rejected: one bad entry in a replayed queue must not throw away
            # the rest of the batch.
            continue
        current = existing.get(item.id)
        if current is None:
            s.add(
                ExamAnswer(
                    item_id=item.id,
                    session_id=row.id,
                    selected_label=incoming.selected_label,
                    value=incoming.value,
                    flagged=incoming.flagged,
                    client_seq=incoming.client_seq,
                )
            )
        elif incoming.client_seq >= current.client_seq:
            # Equal counts as newer so a retry of the same sequence is
            # idempotent rather than being dropped.
            current.selected_label = incoming.selected_label
            current.value = incoming.value
            current.flagged = incoming.flagged
            current.client_seq = incoming.client_seq
            current.answered_at = datetime.now(timezone.utc)
        # A lower sequence is a stale queued answer arriving late. Ignored:
        # this is the whole reason the sequence exists.

    s.flush()
    return _session_out(s, row, with_items=False)


@router.post("/sessions/{session_id}/submit", response_model=ExamSessionOut)
def submit_session(
    session_id: str,
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.require_account_csrf),
) -> ExamSessionOut:
    """Submit, and only now mark. Irreversible."""
    row = _owned(s, session_id, v)
    if row.submitted_at is not None:
        # Idempotent rather than an error: a student whose connection dropped
        # during submission will press it again, and they should see their
        # result rather than a failure.
        return _session_out(s, row, with_items=True)

    pairs = s.execute(
        select(ExamSessionItem, Question, ExamAnswer)
        .join(Question, Question.id == ExamSessionItem.question_id)
        .outerjoin(ExamAnswer, ExamAnswer.item_id == ExamSessionItem.id)
        .where(ExamSessionItem.session_id == row.id)
    ).all()

    correct = 0
    for item, question, answer in pairs:
        if answer is None:
            continue
        answer.correct = _mark(question, answer)
        correct += 1 if answer.correct else 0

    total = len(pairs)
    scale = float((row.format_snapshot or {}).get("scoring", {}).get("scale_max", 100))
    row.score = round(scale * correct / total, 2) if total else 0.0
    row.scale_max = scale
    row.submitted_at = datetime.now(timezone.utc)
    s.flush()
    return _session_out(s, row, with_items=True)


@router.get("/sessions/{session_id}/result", response_model=ExamResultOut)
def get_result(
    session_id: str,
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.require_account),
) -> ExamResultOut:
    """Score in the exam's own scale, broken down by section and topic."""
    row = _owned(s, session_id, v)
    if row.submitted_at is None:
        raise api_deps.problem(
            409,
            "conflict",
            "That exam has not been submitted yet, so there is no result to show.",
        )

    pairs = s.execute(
        select(ExamSessionItem, Question, ExamAnswer)
        .join(Question, Question.id == ExamSessionItem.question_id)
        .outerjoin(ExamAnswer, ExamAnswer.item_id == ExamSessionItem.id)
        .where(ExamSessionItem.session_id == row.id)
    ).all()

    sections: dict[str, dict] = {}
    wrong_topics: dict[str, int] = {}
    correct = 0
    for item, question, answer in pairs:
        bucket = sections.setdefault(
            item.section_key, {"correct": 0, "total": 0}
        )
        bucket["total"] += 1
        if answer and answer.correct:
            bucket["correct"] += 1
            correct += 1
        elif question.topic:
            wrong_topics[question.topic] = wrong_topics.get(question.topic, 0) + 1

    snapshot = row.format_snapshot or {}
    titles = {s_["key"]: s_["title"] for s_ in snapshot.get("sections", [])}
    per_section_max = float(
        snapshot.get("scoring", {}).get("per_section_max", 0) or 0
    )

    started = row.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    submitted = row.submitted_at
    if submitted.tzinfo is None:
        submitted = submitted.replace(tzinfo=timezone.utc)

    return ExamResultOut(
        session_id=str(row.id),
        score=row.score or 0.0,
        scale_max=row.scale_max or 0.0,
        correct=correct,
        total=len(pairs),
        seconds_taken=int((submitted - started).total_seconds()),
        sections=[
            ExamResultSection(
                key=key,
                title=titles.get(key, key),
                correct=data["correct"],
                total=data["total"],
                score=round(
                    per_section_max * data["correct"] / data["total"], 2
                )
                if per_section_max and data["total"]
                else 0.0,
            )
            for key, data in sections.items()
        ],
        weakest_topics=[
            t for t, _ in sorted(wrong_topics.items(), key=lambda kv: -kv[1])[:5]
        ],
    )
