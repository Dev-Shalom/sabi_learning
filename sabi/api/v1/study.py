"""Practice, reading, the notebook, and onboarding.

Practice and exam mode differ in exactly one respect and it is deliberate:
**practice marks as you go, exam mode does not.** A student practising wants
to know immediately and to see why the distractor tempted them; a student
sitting a mock is rehearsing the real thing, where nothing is known until the
end. Both are here rather than in one shared "answer a question" route,
because collapsing them would eventually collapse the distinction.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sabi.api.deps import Viewer
from sabi.api.v1 import deps as api_deps
from sabi.api.v1.catalog import servable
from sabi.api.v1.exam import _question_out, _source_label
from sabi.api.v1.schemas import (
    MarkingOut,
    OnboardingIn,
    OnboardingOut,
    PageOut,
    PracticeAnswerRequest,
    PracticeItemOut,
    PracticeSetOut,
    PracticeSetRequest,
)
from sabi.models import (
    Passage,
    PracticeItem,
    PracticeResponse,
    PracticeSet,
    Question,
    StudentProfile,
    Subject,
)

router = APIRouter()


# ----------------------------------------------------------------- practice


@router.post(
    "/practice/sets", response_model=PracticeSetOut, status_code=201, tags=["practice"]
)
def build_set(
    body: PracticeSetRequest,
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.require_csrf_header),
) -> PracticeSetOut:
    """Draw a practice set from the bank.

    Only servable questions, and `func.random()` rather than a fixed order so
    two sets on the same topic are not the same set.
    """
    subject = s.get(Subject, body.subject_code.upper())
    if subject is None or not subject.available:
        raise api_deps.problem(
            404, "not_found", "That subject is not open for practice yet."
        )

    stmt = servable(
        select(Question).where(
            Question.subject_code == subject.code,
            Question.exam_body == body.exam_body,
        )
    )
    if body.year:
        stmt = stmt.where(Question.year == body.year)
    if body.topic:
        stmt = stmt.where(Question.topic == body.topic)

    pool = s.execute(stmt.order_by(func.random()).limit(body.count)).scalars().all()
    if not pool:
        raise api_deps.problem(
            404,
            "not_found",
            "There are no questions for that combination yet. Try another "
            "year or topic.",
        )

    row = PracticeSet(
        user_id=v.user.id,
        subject=subject.name,
        exam_board=body.exam_body,
        topic=body.topic,
        built_from="bank",
        seconds_allowed=0,
    )
    s.add(row)
    s.flush()

    for position, question in enumerate(pool):
        s.add(
            PracticeItem(
                set_id=row.id,
                position=position,
                template_id="bank",
                source_doc_id=question.id,
                source_locator=_source_label(question),
                params={},
                topic=question.topic or "",
                subtopic=question.subtopic or "",
                question=question.stem,
                answer=(question.answer or {}).get("key")
                or (question.answer or {}).get("value", ""),
                answer_kind="text" if question.type == "objective" else "number",
                hint="",
                working={},
            )
        )
    s.flush()
    return _set_out(s, row)


def _set_out(s: Session, row: PracticeSet) -> PracticeSetOut:
    items = (
        s.execute(
            select(PracticeItem)
            .where(PracticeItem.set_id == row.id)
            .order_by(PracticeItem.position)
        )
        .scalars()
        .all()
    )
    questions = {
        q.id: q
        for q in s.execute(
            select(Question).where(
                Question.id.in_([i.source_doc_id for i in items])
            )
        ).scalars()
    }
    responses = {
        r.item_id: r
        for r in s.execute(
            select(PracticeResponse).where(PracticeResponse.set_id == row.id)
        ).scalars()
    }

    out: list[PracticeItemOut] = []
    for item in items:
        question = questions.get(item.source_doc_id)
        if question is None:
            continue
        response = responses.get(item.id)
        marking = None
        if response is not None:
            marking = _marking(question, response.correct, response.given)
        out.append(
            PracticeItemOut(
                id=item.id,
                position=item.position,
                question=_question_out(question),
                answered=response is not None,
                given=response.given if response else None,
                marking=marking,
            )
        )

    return PracticeSetOut(
        id=row.id,
        subject_code=_code_of(s, row.subject),
        exam_body=row.exam_board,
        created_at=row.created_at,
        items=out,
    )


def _code_of(s: Session, subject_name: str) -> str:
    code = s.execute(
        select(Subject.code).where(Subject.name == subject_name)
    ).scalar_one_or_none()
    return code or ""


def _marking(question: Question, correct: bool, given: str | None) -> MarkingOut:
    explanation = question.explanation or {}
    why = None
    if not correct and given:
        chosen = next(
            (o for o in (question.options or []) if o.get("label") == given), None
        )
        why = (chosen or {}).get("why_wrong")
    return MarkingOut(
        correct=bool(correct),
        correct_label=(question.answer or {}).get("key"),
        correct_value=(question.answer or {}).get("value"),
        explanation=explanation.get("text"),
        why_wrong=why,
        locators=explanation.get("locators", []),
    )


@router.get("/practice/sets/{set_id}", response_model=PracticeSetOut, tags=["practice"])
def get_set(
    set_id: int,
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.api_viewer),
) -> PracticeSetOut:
    row = s.get(PracticeSet, set_id)
    if row is None or row.user_id != v.user.id:
        raise api_deps.problem(404, "not_found", "No such practice set.")
    return _set_out(s, row)


@router.post(
    "/practice/sets/{set_id}/answer", response_model=MarkingOut, tags=["practice"]
)
def answer_practice(
    set_id: int,
    body: PracticeAnswerRequest,
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.require_csrf_header),
) -> MarkingOut:
    """Answer one practice question, and get it marked immediately.

    This is what separates practice from exam mode, and it is the only place
    the two behave differently on purpose.
    """
    row = s.get(PracticeSet, set_id)
    if row is None or row.user_id != v.user.id:
        raise api_deps.problem(404, "not_found", "No such practice set.")

    item = s.execute(
        select(PracticeItem).where(
            PracticeItem.set_id == row.id,
            PracticeItem.source_doc_id == body.question_id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise api_deps.problem(404, "not_found", "That question is not in this set.")

    question = s.get(Question, body.question_id)
    if question is None:
        raise api_deps.problem(404, "not_found", "That question no longer exists.")

    given = body.selected_label or body.value or ""
    if question.type == "objective":
        correct = bool(
            body.selected_label
            and body.selected_label == (question.answer or {}).get("key")
        )
    else:
        from sabi.valuematch import answers_match

        expected = (question.answer or {}).get("value", "")
        kind = (question.answer or {}).get("value_kind", "number")
        correct = bool(expected and answers_match(expected, given, kind))

    existing = s.execute(
        select(PracticeResponse).where(PracticeResponse.item_id == item.id)
    ).scalar_one_or_none()
    if existing is None:
        s.add(
            PracticeResponse(
                item_id=item.id,
                set_id=row.id,
                user_id=v.user.id,
                subject=row.subject,
                subtopic=item.subtopic,
                given=given[:255],
                correct=correct,
            )
        )
    else:
        # Changing an answer updates the row rather than adding one, or a
        # student could raise their own correct-rate by resubmitting.
        existing.given = given[:255]
        existing.correct = correct
        existing.answered_at = datetime.now(timezone.utc)
    s.flush()

    return _marking(question, correct, given)


# ------------------------------------------------------------------ reading


@router.get("/reading/questions", response_model=PageOut, tags=["reading"])
def read_questions(
    subject_code: str,
    exam_body: str = "WAEC",
    year: int | None = None,
    topic: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.api_viewer),
) -> PageOut:
    """Past questions with their answers and explanations visible.

    Cursor-paginated and capped at 50. There is no "give me everything": the
    question bank is the asset, and a bulk export endpoint would hand it over.
    """
    stmt = servable(
        select(Question).where(
            Question.subject_code == subject_code.upper(),
            Question.exam_body == exam_body,
        )
    )
    if year:
        stmt = stmt.where(Question.year == year)
    if topic:
        stmt = stmt.where(Question.topic == topic)
    if cursor:
        stmt = stmt.where(Question.id > cursor)

    rows = s.execute(stmt.order_by(Question.id).limit(limit + 1)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    passages = {
        p.id: p.text
        for p in s.execute(
            select(Passage).where(
                Passage.id.in_([r.passage_id for r in rows if r.passage_id])
            )
        ).scalars()
    }

    items = []
    for q in rows:
        explanation = q.explanation or {}
        items.append(
            {
                "question": _question_out(q, passages.get(q.passage_id)).model_dump(),
                "answer": {
                    "label": (q.answer or {}).get("key"),
                    "value": (q.answer or {}).get("value"),
                },
                "explanation": explanation.get("text"),
                "locators": explanation.get("locators", []),
            }
        )

    return PageOut(items=items, next_cursor=rows[-1].id if has_more and rows else None)


# --------------------------------------------------------------- onboarding


@router.get("/onboarding", response_model=OnboardingOut, tags=["onboarding"])
def get_onboarding(
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.require_account),
) -> OnboardingOut:
    row = s.get(StudentProfile, v.user.id)
    if row is None:
        return OnboardingOut(completed=False)
    return OnboardingOut(
        school_class=row.school_class,
        track=row.track,
        exams=row.exams or [],
        subjects=row.subjects or {},
        exam_dates=row.exam_dates or {},
        target=row.target,
        weak_topics=row.weak_topics or [],
        daily_minutes=row.daily_minutes,
        completed=row.completed_at is not None,
    )


@router.put("/onboarding", response_model=OnboardingOut, tags=["onboarding"])
def save_onboarding(
    body: OnboardingIn,
    s: Session = Depends(api_deps.db),
    v: Viewer = Depends(api_deps.require_account_csrf),
) -> OnboardingOut:
    """Save the answers, enforcing each exam's combination rules.

    A broken rule is explained rather than silently rejected: the message says
    which rule and why, because a student who cannot see the rule cannot fix
    their choice.
    """
    problems = _check_combinations(s, body)
    if problems:
        raise api_deps.problem(422, "bad_request", " ".join(problems))

    row = s.get(StudentProfile, v.user.id)
    if row is None:
        row = StudentProfile(user_id=v.user.id)
        s.add(row)

    row.school_class = body.school_class
    row.track = body.track
    row.exams = body.exams
    row.subjects = body.subjects
    row.exam_dates = body.exam_dates
    row.target = body.target
    row.weak_topics = body.weak_topics
    row.daily_minutes = body.daily_minutes
    # Complete once the two required answers are present. Everything else is
    # volunteered and can be filled in later from settings.
    if body.school_class and body.track and row.completed_at is None:
        row.completed_at = datetime.now(timezone.utc)
    s.flush()

    return get_onboarding(s=s, v=v)


def _check_combinations(s: Session, body: OnboardingIn) -> list[str]:
    """Each exam's own rules, read from its format config rather than guessed."""
    from sabi.content import formats

    known = {
        r.code
        for r in s.execute(select(Subject)).scalars()
    }
    problems: list[str] = []

    for exam_body, codes in (body.subjects or {}).items():
        unknown = [c for c in codes if c.upper() not in known]
        if unknown:
            problems.append(f"Sabi does not know these subjects: {', '.join(unknown)}.")
            continue

        rules = {}
        for fmt in formats.for_body(exam_body):
            rules = fmt.data.get("subject_rules", {}) or {}
            break
        if not rules:
            continue

        minimum = rules.get("min_subjects")
        maximum = rules.get("max_subjects")
        if minimum and len(codes) < minimum:
            problems.append(
                f"{exam_body} needs {minimum} subjects and you have chosen "
                f"{len(codes)}."
            )
        if maximum and len(codes) > maximum:
            problems.append(
                f"{exam_body} allows {maximum} subjects and you have chosen "
                f"{len(codes)}."
            )

        for name in rules.get("compulsory", []) or []:
            code = s.execute(
                select(Subject.code).where(Subject.name == name)
            ).scalar_one_or_none()
            if code and code not in [c.upper() for c in codes]:
                problems.append(f"{name} is compulsory for {exam_body}.")

    return problems
