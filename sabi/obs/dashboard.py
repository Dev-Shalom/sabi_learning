"""What a student sees about their own studying.

All reads. Nothing here needs a new write path, because the request log already
records everything worth showing: what was asked, which chunks were cited,
whether it was refused, and when. `ix_requests_user_created` is already the
right index for it.

Two things are deliberately not on this page. Cost per question, because a
16-year-old being shown what they cost is a strange thing to do to them and it
is an internal number -- `sabi report` is where that lives. And anything
derived from another student's data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from sabi.limits.limiter import COUNTED_EVENTS, wat_today
from sabi.models import Request as RequestRow
from sabi.models import UsageEvent, User

RECENT_LIMIT = 8
TOPIC_LIMIT = 6


@dataclass
class Summary:
    asked_total: int = 0
    asked_today: int = 0
    answered: int = 0
    refused: int = 0
    days_studied: int = 0
    streak: int = 0
    best_streak: int = 0
    first_day: date | None = None
    days_to_exam: int | None = None

    @property
    def answered_share(self) -> int:
        """Whole percent of questions that produced an answer."""
        if not self.asked_total:
            return 0
        return round(100 * self.answered / self.asked_total)


@dataclass
class TopicRow:
    topic: str
    asked: int
    refused: int

    @property
    def answered(self) -> int:
        return self.asked - self.refused

    @property
    def share(self) -> int:
        if not self.asked:
            return 0
        return round(100 * self.answered / self.asked)


@dataclass
class RecentRow:
    request_id: str
    question: str
    created_at: datetime
    refused: bool
    locators: list[str] = field(default_factory=list)


def _study_days(s: Session, user: User) -> list[date]:
    """Distinct days this identity asked something, most recent first."""
    rows = s.execute(
        select(UsageEvent.day)
        .where(
            UsageEvent.user_id == user.id,
            UsageEvent.event_type.in_(COUNTED_EVENTS),
        )
        .group_by(UsageEvent.day)
        .order_by(UsageEvent.day.desc())
    ).scalars()
    return [d for d in rows]


def _streaks(days: list[date], today: date) -> tuple[int, int]:
    """(current, best) runs of consecutive days.

    A streak counts as unbroken if the most recent day is today or yesterday,
    so somebody who studies in the evening does not lose it at midnight.
    """
    if not days:
        return 0, 0

    best = run = 1
    for earlier, later in zip(days[1:], days[:-1]):
        if (later - earlier).days == 1:
            run += 1
        else:
            run = 1
        best = max(best, run)

    current = 0
    if (today - days[0]).days <= 1:
        current = 1
        for earlier, later in zip(days[1:], days[:-1]):
            if (later - earlier).days == 1:
                current += 1
            else:
                break
    return current, best


def summary(s: Session, user: User) -> Summary:
    total = int(
        s.execute(
            select(func.count())
            .select_from(RequestRow)
            .where(RequestRow.user_id == user.id, RequestRow.client == "web")
        ).scalar_one()
    )

    refused = int(
        s.execute(
            select(func.count())
            .select_from(RequestRow)
            .where(
                RequestRow.user_id == user.id,
                RequestRow.client == "web",
                RequestRow.refused.is_(True),
            )
        ).scalar_one()
    )

    today = wat_today()
    asked_today = int(
        s.execute(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                UsageEvent.user_id == user.id,
                UsageEvent.day == today,
                UsageEvent.event_type.in_(COUNTED_EVENTS),
            )
        ).scalar_one()
    )

    days = _study_days(s, user)
    current, best = _streaks(days, today)

    to_exam = None
    if user.exam_date is not None:
        to_exam = (user.exam_date - today).days

    return Summary(
        asked_total=total,
        asked_today=asked_today,
        answered=total - refused,
        refused=refused,
        days_studied=len(days),
        streak=current,
        best_streak=best,
        first_day=days[-1] if days else None,
        days_to_exam=to_exam,
    )


# Topics come from the provenance of the chunks an answer actually cited, so
# this reflects what a student has been answered about rather than what they
# typed. Refusals cite nothing, so they are counted from the request row and
# attributed to the topic that was retrieved.
TOPICS_SQL = text(
    """
    SELECT COALESCE(c.provenance ->> 'topic', 'Unsorted') AS topic,
           COUNT(DISTINCT r.id) AS asked,
           COUNT(DISTINCT r.id) FILTER (WHERE r.refused) AS refused
    FROM requests r
    -- The unnested column is aliased through a table alias: bare `AS ref`
    -- collides with `chunks.ref` once the join below is added, and Postgres
    -- rejects the reference as ambiguous.
    JOIN LATERAL unnest(
        CASE WHEN r.refused THEN r.retrieved_refs ELSE r.cited_refs END
    ) AS u(ref) ON true
    JOIN chunks c ON c.ref = u.ref
    WHERE r.user_id = :user_id
      AND r.client = 'web'
      AND COALESCE(array_length(
            CASE WHEN r.refused THEN r.retrieved_refs ELSE r.cited_refs END, 1
          ), 0) > 0
    GROUP BY 1
    ORDER BY asked DESC, topic
    LIMIT :lim
    """
)


def topics(s: Session, user: User, limit: int = TOPIC_LIMIT) -> list[TopicRow]:
    rows = s.execute(
        TOPICS_SQL, {"user_id": str(user.id), "lim": limit}
    ).all()
    return [TopicRow(topic=r[0], asked=int(r[1]), refused=int(r[2])) for r in rows]


def recent(s: Session, user: User, limit: int = RECENT_LIMIT) -> list[RecentRow]:
    rows = s.execute(
        select(
            RequestRow.id,
            RequestRow.question,
            RequestRow.created_at,
            RequestRow.refused,
            RequestRow.cited_refs,
        )
        .where(RequestRow.user_id == user.id, RequestRow.client == "web")
        .order_by(RequestRow.created_at.desc())
        .limit(limit)
    ).all()

    out: list[RecentRow] = []
    for rid, question, created, refused, cited in rows:
        locators = sorted({r.split("#", 1)[0] for r in (cited or [])})[:3]
        out.append(
            RecentRow(
                request_id=str(rid),
                question=question,
                created_at=created,
                refused=bool(refused),
                locators=locators,
            )
        )
    return out


def relative_day(when: datetime, today: date) -> str:
    """'Today', 'Yesterday', or a date. Read by a student, not a log parser."""
    day = when.date()
    delta = (today - day).days
    if delta <= 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    if delta < 7:
        return f"{delta} days ago"
    return day.strftime("%d %b")


def exam_phrase(days: int | None) -> str:
    if days is None:
        return ""
    if days < 0:
        return "already sat"
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days < 14:
        return f"in {days} days"
    weeks = days // 7
    return f"in {weeks} weeks"
