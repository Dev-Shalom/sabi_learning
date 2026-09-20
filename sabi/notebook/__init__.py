"""Answers a student chose to keep.

The whole feature is one idea: a saved answer must still say the same thing
in three weeks. The corpus will have moved by then -- documents edited, chunks
re-split, a locator reassigned -- so a notebook that re-rendered live against
today's corpus would silently change what somebody revised from. That is the
failure this product exists to avoid, arriving through a side door.

So saving copies the answer, its citations and the passages behind them. The
`request_id` link is kept for provenance, but nothing on the page depends on
it still resolving.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from sabi.models import NotebookEntry, Request as RequestRow, User

MAX_NOTE = 600

# Carried into every saved answer, because a student revising from their
# notebook weeks later needs the same warning the answer page gave them.
DISCLOSURE = (
    "Sabi can be wrong. Check with your teacher or the syllabus before you "
    "trust it in an exam."
)


@dataclass
class SavedCitation:
    """One citation, as it read when it was saved."""

    locator: str
    title: str
    attribution: str
    text: str
    highlight: str | None = None


@dataclass
class SavedAnswer:
    """A notebook entry, unpacked for rendering."""

    id: int
    question: str
    answer: str
    subject: str
    exam_board: str
    topic: str | None
    note: str | None
    created_at: datetime
    citations: list[SavedCitation]
    disclosure: str
    request_id: str | None

    @property
    def locators(self) -> list[str]:
        return [c.locator for c in self.citations]


def _unpack(row: NotebookEntry) -> SavedAnswer:
    snap = row.snapshot or {}
    return SavedAnswer(
        id=row.id,
        question=row.question,
        answer=snap.get("answer", ""),
        subject=row.subject,
        exam_board=row.exam_board,
        topic=row.topic,
        note=row.note,
        created_at=row.created_at,
        citations=[
            SavedCitation(
                locator=c.get("locator", ""),
                title=c.get("title", ""),
                attribution=c.get("attribution", ""),
                text=c.get("text", ""),
                highlight=c.get("highlight"),
            )
            for c in snap.get("citations", [])
        ],
        disclosure=snap.get("disclosure", ""),
        request_id=str(row.request_id) if row.request_id else None,
    )


def save(
    s: Session,
    *,
    user: User,
    request: RequestRow,
    result,
    note: str | None = None,
) -> NotebookEntry:
    """Keep this answer.

    `result` is the `AnswerResult` that produced the page, which already
    carries the citations with their source text and the highlighted span --
    so the snapshot is taken from what the student actually saw, not
    reconstructed from the corpus afterwards.

    Saving the same answer twice updates the note rather than adding a row.
    """
    snapshot = {
        "answer": result.text,
        "disclosure": getattr(result, "disclosure", ""),
        "refused": bool(getattr(result, "refused", False)),
        "citations": [
            {
                "locator": c.locator,
                "title": c.title,
                "attribution": c.attribution,
                "text": c.text,
                "highlight": getattr(c, "highlight", None),
            }
            for c in getattr(result, "citations", [])
        ],
    }

    # The topic comes from the chunk that was actually cited, looked up once
    # here rather than stored on the citation -- `Citation` carries what the
    # page needs to render, and topic is not part of that.
    topic = None
    refs = [c.ref for c in getattr(result, "citations", []) if getattr(c, "ref", None)]
    if refs:
        from sabi.models import Chunk

        row = s.execute(
            select(Chunk.provenance).where(Chunk.ref.in_(refs)).limit(1)
        ).scalar_one_or_none()
        if row:
            topic = row.get("subtopic") or row.get("topic")

    existing = s.execute(
        select(NotebookEntry).where(
            NotebookEntry.user_id == user.id,
            NotebookEntry.request_id == request.id,
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.note = (note or "").strip()[:MAX_NOTE] or None
        existing.snapshot = snapshot
        return existing

    row = NotebookEntry(
        user_id=user.id,
        request_id=request.id,
        question=request.question,
        subject=request.subject,
        exam_board=request.exam_board,
        topic=topic,
        note=(note or "").strip()[:MAX_NOTE] or None,
        snapshot=snapshot,
    )
    s.add(row)
    s.flush()
    return row


def save_from_request(
    s: Session,
    *,
    user: User,
    request: RequestRow,
    note: str | None = None,
) -> NotebookEntry:
    """Keep an answer, rebuilt from the stored request row.

    Saving happens on a separate POST from answering, so the `AnswerResult`
    is long gone by then. Re-answering to get it back would cost a question
    from the student's allowance and could produce different text from what
    they actually read, which is the one thing a notebook must not do.

    Everything needed is already recorded: the answer text on the request,
    and `cited_refs` pointing at the chunks behind it. The underline is
    recomputed with the same function the answer page used, against the same
    two inputs, so it lands in the same place.
    """
    from sabi.answer.service import _highlight, citation_body
    from sabi.models import Chunk

    answer = request.answer or ""
    refs = list(request.cited_refs or [])

    citations: list[dict] = []
    if refs:
        rows = s.execute(
            select(Chunk).where(Chunk.ref.in_(refs))
        ).scalars().all()
        by_ref = {c.ref: c for c in rows}

        # Grouped by locator, exactly as the answer page groups them: sibling
        # chunks of one document are one source, not two near-identical
        # panels. `citation_body` is the same function the page used, so the
        # text is byte-identical and the underline lands in the same place.
        for locator in dict.fromkeys(
            by_ref[r].locator for r in refs if r in by_ref
        ):
            parts = [
                by_ref[r] for r in refs
                if r in by_ref and by_ref[r].locator == locator
            ]
            if not parts:
                # Re-split or removed since. The answer still stands; it
                # loses that panel rather than showing an empty one.
                continue
            prov = parts[0].provenance or {}
            body = citation_body(parts)
            citations.append({
                "locator": locator,
                "title": prov.get("title", ""),
                "attribution": prov.get("attribution", ""),
                "text": body,
                "highlight": _highlight(body, answer),
            })

    topic = None
    for ref in refs:
        chunk = s.execute(
            select(Chunk.provenance).where(Chunk.ref == ref)
        ).scalar_one_or_none()
        if chunk:
            topic = chunk.get("subtopic") or chunk.get("topic")
            if topic:
                break

    snapshot = {
        "answer": answer,
        "disclosure": DISCLOSURE,
        "refused": bool(request.refused),
        "citations": citations,
    }

    existing = s.execute(
        select(NotebookEntry).where(
            NotebookEntry.user_id == user.id,
            NotebookEntry.request_id == request.id,
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.note = (note or "").strip()[:MAX_NOTE] or None
        existing.snapshot = snapshot
        return existing

    row = NotebookEntry(
        user_id=user.id,
        request_id=request.id,
        question=request.question,
        subject=request.subject,
        exam_board=request.exam_board,
        topic=topic,
        note=(note or "").strip()[:MAX_NOTE] or None,
        snapshot=snapshot,
    )
    s.add(row)
    s.flush()
    return row


def remove(s: Session, *, user: User, entry_id: int) -> bool:
    """Delete one entry. Scoped to the owner, so an id alone is not enough."""
    result = s.execute(
        delete(NotebookEntry).where(
            NotebookEntry.id == entry_id, NotebookEntry.user_id == user.id
        )
    )
    return bool(result.rowcount)


def listing(
    s: Session, *, user: User, subject: str | None = None, limit: int = 100
) -> list[SavedAnswer]:
    stmt = select(NotebookEntry).where(NotebookEntry.user_id == user.id)
    if subject:
        stmt = stmt.where(NotebookEntry.subject == subject)
    stmt = stmt.order_by(NotebookEntry.created_at.desc()).limit(limit)
    return [_unpack(r) for r in s.execute(stmt).scalars()]


def count(s: Session, *, user: User) -> int:
    return int(
        s.execute(
            select(func.count())
            .select_from(NotebookEntry)
            .where(NotebookEntry.user_id == user.id)
        ).scalar_one()
    )


def subjects(s: Session, *, user: User) -> list[tuple[str, int]]:
    """Subjects this student has saved from, with counts, for the filter."""
    rows = s.execute(
        select(NotebookEntry.subject, func.count())
        .where(NotebookEntry.user_id == user.id)
        .group_by(NotebookEntry.subject)
        .order_by(func.count().desc())
    ).all()
    return [(r[0], int(r[1])) for r in rows]


def is_saved(s: Session, *, user: User, request_id) -> bool:
    return (
        s.execute(
            select(NotebookEntry.id).where(
                NotebookEntry.user_id == user.id,
                NotebookEntry.request_id == request_id,
            )
        ).scalar_one_or_none()
        is not None
    )


def saved_at(row: NotebookEntry) -> datetime:
    return row.created_at or datetime.now(timezone.utc)
