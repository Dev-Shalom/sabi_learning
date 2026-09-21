"""Timed practice.

Deliberately not called a mock exam. A mock exam implies past papers under
licence and a mark scheme somebody else wrote; this is a set of questions
generated from the worked examples in the corpus, and calling it what it is
costs nothing and keeps a claim we cannot support out of the product.

Three things here are worth knowing before reading the code:

**Answers are marked, not judged.** `sabi.valuematch` decides whether what a
student typed is the value that was computed. No model is involved, nothing
is asked of an API, and a practice set costs nothing to sit.

**A wrong answer ends at a citation.** Every item carries the `doc_id` and
locator of the worked example its template came from, so the explanation a
student sees is the worked example in the corpus, not generated prose. That
is the same rule the answer path follows.

**Weak topics are a correct-rate, not a model.** A rolling proportion over
recent answers in a subtopic, with a floor on how many answers count as
evidence. It is explainable to a sixteen-year-old in one sentence, which
matters more here than anything a mastery model would buy.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sabi.models import PracticeItem, PracticeResponse, PracticeSet, User
from sabi.practice import templates as templates_mod
from sabi.valuematch import answers_match

# A set is this many questions. Short enough to finish in one sitting on a
# phone, long enough that the score is not decided by a single slip.
SET_SIZE = 8

# The clock. Roughly two minutes a question, which is the pace of the real
# paper rather than a number chosen for tidiness.
SECONDS_ALLOWED = 15 * 60

# Sets a student may start in one day. Generating a set costs no API calls,
# so this is not a spend limit -- it is the bound that stops an automated
# client filling the table, which nothing else here would notice.
DAILY_SET_CAP = 40

# Weak-topic detection. A subtopic needs this many answers before it is
# called weak, so one bad morning does not rewrite a student's dashboard.
WEAK_MIN_ANSWERS = 4
WEAK_WINDOW = 12
WEAK_AT = 0.6


@dataclass
class ItemView:
    """One question, as the page renders it."""

    id: int
    position: int
    question: str
    hint: str
    answer_kind: str
    subtopic: str
    locator: str
    doc_id: str
    # Filled in only once the set is finished.
    given: str | None = None
    correct: bool | None = None
    expected: str | None = None
    working: tuple[str, ...] = ()

    @property
    def answered(self) -> bool:
        return self.given is not None


@dataclass
class SetView:
    id: int
    subject: str
    exam_board: str
    topic: str | None
    built_from: str
    seconds_allowed: int
    created_at: datetime
    finished_at: datetime | None
    items: list[ItemView]

    @property
    def finished(self) -> bool:
        return self.finished_at is not None

    @property
    def answered_count(self) -> int:
        return sum(1 for i in self.items if i.answered)

    @property
    def score(self) -> int:
        return sum(1 for i in self.items if i.correct)

    @property
    def seconds_taken(self) -> int:
        end = self.finished_at or datetime.now(timezone.utc)
        return max(0, int((end - self.created_at).total_seconds()))

    @property
    def weak_locators(self) -> list[str]:
        return [i.locator for i in self.items if i.correct is False]


# ------------------------------------------------------------------ building


def sets_today(s: Session, *, user: User) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    return int(
        s.execute(
            select(func.count())
            .select_from(PracticeSet)
            .where(PracticeSet.user_id == user.id, PracticeSet.created_at >= since)
        ).scalar_one()
    )


def build_set(
    s: Session,
    *,
    user: User,
    subject: str,
    exam_board: str = "WAEC",
    topic: str | None = None,
    size: int = SET_SIZE,
    rng: random.Random | None = None,
) -> PracticeSet:
    """Generate and store a fresh set.

    `topic` restricts to one subtopic. With no topic, the set is drawn across
    the subject, weighted towards whatever the student has recently been
    getting wrong -- so practice drifts to where it is needed without anyone
    having to choose.
    """
    rng = rng or random.Random()
    pool = templates_mod.for_scope(subject, exam_board)
    if topic:
        pool = [t for t in pool if t.subtopic == topic]
    if not pool:
        raise ValueError(f"no practice templates for {exam_board}:{subject}")

    weak = {row.subtopic for row in weak_subtopics(s, user=user, subject=subject)}
    built_from = "topic" if topic else ("weak" if weak else "mixed")

    chosen = _choose(pool, size, weak, rng)

    row = PracticeSet(
        user_id=user.id,
        subject=subject,
        exam_board=exam_board,
        topic=topic,
        built_from=built_from,
        seconds_allowed=SECONDS_ALLOWED,
    )
    s.add(row)
    s.flush()

    for position, template in enumerate(chosen):
        built = template.sample(rng)
        s.add(
            PracticeItem(
                set_id=row.id,
                position=position,
                template_id=template.template_id,
                source_doc_id=template.source_doc_id,
                source_locator=template.source_locator,
                params=built.params,
                topic=template.topic,
                subtopic=template.subtopic,
                question=built.question,
                answer=built.answer,
                answer_kind=built.answer_kind,
                hint=built.hint,
                working={"steps": list(built.working)},
            )
        )
    s.flush()
    return row


def _choose(pool, size, weak, rng):
    """Pick the templates for a set.

    Distinct templates first, so a set of eight is eight different questions
    rather than the same shape with different numbers -- which is what makes
    it practice rather than drill. Weak subtopics go in first; the rest is
    filled from the whole pool. Only if the pool is smaller than the set does
    a template appear twice.
    """
    weak_first = [t for t in pool if t.subtopic in weak]
    rest = [t for t in pool if t.subtopic not in weak]
    rng.shuffle(weak_first)
    rng.shuffle(rest)

    chosen: list = []
    taken: set[str] = set()

    def take(candidates, limit):
        for candidate in candidates:
            if len(chosen) >= limit:
                return
            if candidate.template_id in taken:
                continue
            taken.add(candidate.template_id)
            chosen.append(candidate)

    # At most half the set from weak topics: a student who is struggling
    # should still see questions they can get right.
    take(weak_first, max(1, size // 2))
    take(rest, size)
    take(weak_first, size)

    # Only reachable when the pool holds fewer templates than the set size,
    # which is possible for a single-subtopic set.
    while len(chosen) < size:
        chosen.append(rng.choice(pool))

    rng.shuffle(chosen)
    return chosen[:size]


# ------------------------------------------------------------------- marking


def mark(
    s: Session, *, user: User, item_id: int, given: str
) -> PracticeResponse | None:
    """Record and mark one answer. Returns None if the item is not theirs."""
    item = s.get(PracticeItem, item_id)
    if item is None:
        return None
    parent = s.get(PracticeSet, item.set_id)
    if parent is None or parent.user_id != user.id:
        return None
    if parent.finished_at is not None:
        # Marking is over. Accepting an answer now would let a student
        # improve a score they have already seen the answers to.
        return None

    given = (given or "").strip()[:255]
    correct = answers_match(item.answer, given, item.answer_kind)

    existing = s.execute(
        select(PracticeResponse).where(PracticeResponse.item_id == item.id)
    ).scalar_one_or_none()

    if existing is not None:
        existing.given = given
        existing.correct = correct
        existing.answered_at = datetime.now(timezone.utc)
        return existing

    row = PracticeResponse(
        item_id=item.id,
        set_id=parent.id,
        user_id=user.id,
        subject=parent.subject,
        subtopic=item.subtopic,
        given=given,
        correct=correct,
    )
    s.add(row)
    s.flush()
    return row


def finish(s: Session, *, user: User, set_id: int) -> PracticeSet | None:
    """Close a set, revealing the answers."""
    row = s.get(PracticeSet, set_id)
    if row is None or row.user_id != user.id:
        return None
    if row.finished_at is None:
        row.finished_at = datetime.now(timezone.utc)
        s.flush()
    return row


# ------------------------------------------------------------------ reading


def view(s: Session, *, user: User, set_id: int) -> SetView | None:
    row = s.get(PracticeSet, set_id)
    if row is None or row.user_id != user.id:
        return None

    items = (
        s.execute(
            select(PracticeItem)
            .where(PracticeItem.set_id == row.id)
            .order_by(PracticeItem.position)
        )
        .scalars()
        .all()
    )
    responses = {
        r.item_id: r
        for r in s.execute(
            select(PracticeResponse).where(PracticeResponse.set_id == row.id)
        ).scalars()
    }

    finished = row.finished_at is not None
    views: list[ItemView] = []
    for item in items:
        response = responses.get(item.id)
        views.append(
            ItemView(
                id=item.id,
                position=item.position,
                question=item.question,
                hint=item.hint,
                answer_kind=item.answer_kind,
                subtopic=item.subtopic,
                locator=item.source_locator,
                doc_id=item.source_doc_id,
                given=response.given if response else None,
                # Whether an answer was right is withheld until the set is
                # closed. Marking each one as it is typed turns a timed set
                # into a guessing game against the marker.
                correct=(response.correct if response and finished else None),
                expected=item.answer if finished else None,
                working=tuple((item.working or {}).get("steps", [])) if finished else (),
            )
        )

    return SetView(
        id=row.id,
        subject=row.subject,
        exam_board=row.exam_board,
        topic=row.topic,
        built_from=row.built_from,
        seconds_allowed=row.seconds_allowed,
        created_at=row.created_at,
        finished_at=row.finished_at,
        items=views,
    )


@dataclass
class TopicRate:
    subtopic: str
    answered: int
    correct: int

    @property
    def rate(self) -> float:
        return self.correct / self.answered if self.answered else 0.0


def topic_rates(
    s: Session, *, user: User, subject: str | None = None, window: int = WEAK_WINDOW
) -> list[TopicRate]:
    """Correct-rate per subtopic over that subtopic's most recent answers.

    The window is per subtopic rather than global, so a student who has done
    a lot of algebra lately still has a meaningful geometry rate instead of
    one computed from whatever fell inside the last N answers overall.
    """
    stmt = select(PracticeResponse).where(PracticeResponse.user_id == user.id)
    if subject:
        stmt = stmt.where(PracticeResponse.subject == subject)
    stmt = stmt.order_by(PracticeResponse.answered_at.desc())

    seen: dict[str, list[bool]] = {}
    for response in s.execute(stmt).scalars():
        bucket = seen.setdefault(response.subtopic, [])
        if len(bucket) < window:
            bucket.append(bool(response.correct))

    return sorted(
        (
            TopicRate(subtopic=name, answered=len(marks), correct=sum(marks))
            for name, marks in seen.items()
            if name
        ),
        key=lambda r: (r.rate, -r.answered),
    )


def weak_subtopics(
    s: Session, *, user: User, subject: str | None = None
) -> list[TopicRate]:
    """Subtopics a student is getting wrong often enough for it to mean something."""
    return [
        r
        for r in topic_rates(s, user=user, subject=subject)
        if r.answered >= WEAK_MIN_ANSWERS and r.rate < WEAK_AT
    ]


def recent_sets(s: Session, *, user: User, limit: int = 10) -> list[PracticeSet]:
    return list(
        s.execute(
            select(PracticeSet)
            .where(PracticeSet.user_id == user.id)
            .order_by(PracticeSet.created_at.desc())
            .limit(limit)
        ).scalars()
    )


def scores_for(s: Session, *, user: User, set_ids: list[int]) -> dict[int, tuple[int, int]]:
    """(correct, answered) per set, for a list page."""
    if not set_ids:
        return {}
    rows = s.execute(
        select(
            PracticeResponse.set_id,
            func.count(),
            func.count().filter(PracticeResponse.correct),
        )
        .where(PracticeResponse.set_id.in_(set_ids))
        .group_by(PracticeResponse.set_id)
    ).all()
    return {int(r[0]): (int(r[2]), int(r[1])) for r in rows}


def totals(s: Session, *, user: User) -> tuple[int, int]:
    """(correct, answered) over everything, for the dashboard."""
    row = s.execute(
        select(func.count(), func.count().filter(PracticeResponse.correct)).where(
            PracticeResponse.user_id == user.id
        )
    ).one()
    return int(row[1] or 0), int(row[0] or 0)
