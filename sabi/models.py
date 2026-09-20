"""Database schema.

Notes that matter more than the column list:

* `chunks` carries denormalised provenance. Citations render from the chunk,
  not from a join at request time, so a citation can never drift from the text
  it points at.
* `requests` stores everything needed to reconstruct an answer exactly:
  retrieved chunk ids, model, prompt version, retrieval confidence. That is what
  makes a down-vote actionable three weeks later.
* `usage_events` is separate from `requests` on purpose. Requests are an
  engineering log; usage events are the billing-shaped record. Today every event
  is priced at zero on the `free` plan, but the shape does not have to change to
  start charging.
* Nothing identifying is stored anywhere. A user is an opaque anonymous id; IPs
  are stored only as a salted hash, only for the rate limiter.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from sabi.config import settings

EMBEDDING_DIM = settings().embedding_dim


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Document(Base):
    """One corpus source document: a syllabus section or a past question."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(400))
    source: Mapped[str] = mapped_column(String(300))

    # How much we actually know about where this came from. The product's whole
    # claim is honest citation, so this is a first-class field, not a comment.
    #   syllabus      -- text of the published WAEC syllabus
    #   past_question -- an item in circulation, year/number as attributed
    #   worked_example-- authored to illustrate a syllabus point, no exam claim
    attribution: Mapped[str] = mapped_column(String(32))

    exam_board: Mapped[str] = mapped_column(String(32), default="WAEC")
    subject: Mapped[str] = mapped_column(String(64), default="Mathematics")
    level: Mapped[str] = mapped_column(String(16), default="SS3")

    topic: Mapped[str | None] = mapped_column(String(120))
    subtopic: Mapped[str | None] = mapped_column(String(160))
    syllabus_section: Mapped[str | None] = mapped_column(String(24), index=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    paper: Mapped[str | None] = mapped_column(String(32))
    question_no: Mapped[str | None] = mapped_column(String(24))

    # Short human string shown in a citation, e.g. "2018 P2 Q7" or "SYL D2".
    locator: Mapped[str] = mapped_column(String(64))

    body: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_path: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_index"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)

    # Stable across re-ingest of unchanged text: "<doc_id>#<chunk_index>".
    # Citations and the golden dataset both reference this, so it must not be a
    # surrogate integer that shifts when the table is rebuilt.
    ref: Mapped[str] = mapped_column(String(160), unique=True, index=True)

    heading: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)

    # Denormalised so a citation renders from one row.
    locator: Mapped[str] = mapped_column(String(64))

    # Also denormalised from the parent document, so retrieval can be scoped
    # without a join -- and, more to the point, so a *partial* index per scope
    # exists to be matched. The same values sit in `provenance`, but JSONB is
    # not cheaply indexable for this, and an HNSW walk that post-filters on a
    # joined table silently returns fewer candidates than it was asked for.
    subject: Mapped[str] = mapped_column(String(64), default="Mathematics")
    exam_board: Mapped[str] = mapped_column(String(32), default="WAEC")
    # True for a "Not on this syllabus" section. This was an unindexed
    # `heading ILIKE '%not on this syllabus%'` over every chunk, on every
    # request, with the pattern hardcoded as a default argument in two places.
    is_exclusion: Mapped[bool] = mapped_column(Boolean, default=False)

    provenance: Mapped[dict] = mapped_column(JSONB, default=dict)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(String(80))

    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', text)", persisted=True)
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Plan(Base):
    """Limits are read from here, never hardcoded. Seeded from limits.yaml."""

    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(64))
    daily_question_cap: Mapped[int] = mapped_column(Integer)
    daily_ip_cap: Mapped[int] = mapped_column(Integer)
    burst_per_minute: Mapped[int] = mapped_column(Integer)
    monthly_cost_ceiling_usd_per_user: Mapped[float] = mapped_column(Float, default=0.0)
    # Price is null for free. The column exists so that adding a paid plan is a
    # row, not a migration.
    price_ngn_monthly: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base):
    """One identity, anonymous or not.

    An account is not a separate row: signing up sets credentials on the row
    the device already had, so every `requests`, `usage_events` and `feedback`
    row keeps pointing at the same `users.id` and nothing has to be migrated.
    It also means the daily allowance cannot be reset by signing up, which is
    both the simpler implementation and the right anti-abuse answer.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    anon_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    plan: Mapped[str] = mapped_column(
        ForeignKey("plans.name"), default="free", index=True
    )
    # The address as typed, for display. `email_normalised` is what is matched
    # on, and it is the one carrying the uniqueness constraint.
    email: Mapped[str | None] = mapped_column(String(320))
    # Not index=True: the partial unique index `uq_users_email_live` in
    # schema.py POST_DDL already covers the only lookup there is (a live
    # account by address), and a second index on the same column would be
    # redundant. Declaring one here would also be invisible on an existing
    # database, which is what tools/schema_drift.py caught.
    email_normalised: Mapped[str | None] = mapped_column(String(320))
    # scrypt, with its parameters inside the value so they can be raised later
    # and old hashes still verified. Null for an anonymous identity.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    signed_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when this row has been folded into another. The unique index on
    # `email_normalised` is partial on this being null, so a merged-away row
    # releases its address.
    merged_into_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # The date they sit the paper, for the countdown. Volunteered, never required.
    exam_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Request(Base):
    """One question, everything needed to reconstruct the answer."""

    __tablename__ = "requests"
    __table_args__ = (
        Index("ix_requests_user_created", "user_id", "created_at"),
        Index("ix_requests_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question: Mapped[str] = mapped_column(Text)
    question_norm_hash: Mapped[str] = mapped_column(String(64), index=True)

    answer: Mapped[str | None] = mapped_column(Text)
    refused: Mapped[bool] = mapped_column(Boolean, default=False)
    refusal_kind: Mapped[str | None] = mapped_column(String(40))

    retrieved_refs: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    cited_refs: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    retrieval_confidence: Mapped[float | None] = mapped_column(Float)

    model: Mapped[str | None] = mapped_column(String(80))
    route: Mapped[str] = mapped_column(String(24), default="llm")  # llm|cache|refusal|capped
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt_version: Mapped[str | None] = mapped_column(String(24))

    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 8), default=0)
    # True when cost_usd is a price-list estimate rather than a billed amount --
    # the offline provider makes no API call, and a report that quietly mixes
    # estimated and actual spend is a report that lies.
    cost_is_estimated: Mapped[bool] = mapped_column(Boolean, default=False)

    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    retrieval_ms: Mapped[int] = mapped_column(Integer, default=0)
    generation_ms: Mapped[int] = mapped_column(Integer, default=0)

    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    client: Mapped[str] = mapped_column(String(24), default="web")  # web|eval|cli

    # The retrieval scope this question was asked in. A dashboard breaks usage
    # down by subject, and `promote` copies the pair onto the golden item so a
    # promoted down-vote stays in the slice it came from.
    subject: Mapped[str] = mapped_column(String(64), default="Mathematics")
    exam_board: Mapped[str] = mapped_column(String(32), default="WAEC")


class UsageEvent(Base):
    """Billing-shaped record. Free today; the shape does not change to charge."""

    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_user_day", "user_id", "day"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requests.id", ondelete="SET NULL")
    )
    day: Mapped[datetime] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    plan: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(32))  # question|cache_hit|refusal|capped
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 8), default=0)
    billable: Mapped[bool] = mapped_column(Boolean, default=True)


class Feedback(Base):
    """Schema-compatible with GoldenItem so promotion is a data move."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    vote: Mapped[int] = mapped_column(Integer)  # +1 / -1
    reason: Mapped[str | None] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(Text)

    # Snapshot of what produced the answer, so a flagged answer can be
    # reconstructed even if the corpus or prompt has since changed.
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)

    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promoted_golden_id: Mapped[int | None] = mapped_column(Integer)


class NotebookEntry(Base):
    """An answer a student chose to keep.

    The snapshot is the whole point, and it follows `Feedback.snapshot` for
    the same reason. A saved answer must still read correctly in three weeks,
    and by then the corpus may have been re-chunked, a document edited, or a
    locator reassigned. Rendering a saved answer live against whatever the
    corpus says today would quietly change what a student revised from --
    which is the exact failure this product exists to avoid, arriving by a
    side door.

    So the answer text, its citations and the source passages behind them are
    copied in at save time. `request_id` stays as the link back to how it was
    produced, but nothing about the display depends on it still resolving.
    """

    __tablename__ = "notebook_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requests.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Denormalised so the list page needs no joins and no live corpus lookup.
    question: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(64), default="Mathematics")
    exam_board: Mapped[str] = mapped_column(String(32), default="WAEC")
    topic: Mapped[str | None] = mapped_column(String(120))

    # The student's own words about why they kept it.
    note: Mapped[str | None] = mapped_column(Text)

    # Everything needed to render the answer exactly as it was: the text, the
    # citations, and the source passage behind each one.
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        # One entry per answer per student: saving twice should update the
        # note, not grow the list.
        UniqueConstraint("user_id", "request_id", name="uq_notebook_user_request"),
        Index("ix_notebook_user_created", "user_id", "created_at"),
    )


class GoldenItem(Base):
    """The evaluation set. Seed items and promoted feedback live in one table."""

    __tablename__ = "golden_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    origin: Mapped[str] = mapped_column(String(24), default="seed")  # seed|feedback
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question: Mapped[str] = mapped_column(Text)
    # Null when the item is deliberately unanswerable.
    expected_answer: Mapped[str | None] = mapped_column(Text)
    # Short deterministic string the answer must contain, e.g. "1800" or "3/8".
    expected_value: Mapped[str | None] = mapped_column(String(200))
    # Holds doc_ids, not chunk refs: chunk indices move when a document is
    # edited, and an eval set that breaks on a typo fix is an eval set nobody runs.
    expected_docs: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    answerable: Mapped[bool] = mapped_column(Boolean, default=True)
    # Why it is unanswerable, for the failure report: out_of_syllabus |
    # out_of_subject | not_in_corpus | welfare
    unanswerable_kind: Mapped[str | None] = mapped_column(String(40))

    topic: Mapped[str | None] = mapped_column(String(120))
    difficulty: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(Text)
    source_feedback_id: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Which scope this item measures. A global metric over several subjects
    # cannot detect one subject regressing, so the suite slices on these.
    subject: Mapped[str] = mapped_column(String(64), default="Mathematics")
    exam_board: Mapped[str] = mapped_column(String(32), default="WAEC")


class AnswerCache(Base):
    """Semantic cache. A hit costs one embedding call and a vector lookup."""

    __tablename__ = "answer_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_norm_hash: Mapped[str] = mapped_column(String(64), index=True)
    # Which syllabus this answer was produced for. Two subjects can share a
    # question's wording, and serving one's answer for the other would be the
    # worst possible cache hit.
    scope: Mapped[str] = mapped_column(String(64), default="WAEC:Mathematics")
    question: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    payload: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(64))
    corpus_version: Mapped[str] = mapped_column(String(64))

    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    """A logged-in session.

    A table rather than a signed cookie, for four reasons specific to this
    app: a new table costs nothing under `create_all`; every route already
    holds a database session, so the lookup rides along with work that is
    happening anyway; revocation and "log out everywhere" become possible; and
    it gives the dashboard somewhere to list a student's active devices.

    Named AuthSession because `sqlalchemy.orm.Session` is imported everywhere
    and a second meaning for the word would be a permanent hazard.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Only the hash is stored. The token itself exists in the cookie and
    # nowhere else, so a database dump does not let anyone log in.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Per-session CSRF secret, so rotating the session invalidates every form
    # that was open under the old one.
    csrf_secret: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # For "this was a different device" on the dashboard. Both one-way.
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_agent_hash: Mapped[str | None] = mapped_column(String(64))


class RecoveryCode(Base):
    """One-time codes, shown once at signup.

    There is no email transport in this deployment, so a password reset has no
    way to reach anyone. Codes are the transport-free answer: hashed the same
    way a password is, single use, and useless to anyone reading the database.
    """

    __tablename__ = "recovery_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginAttempt(Base):
    """Every login try, so repeated failures can be slowed down.

    The existing limiter counts questions, not logins, so it offers no
    protection here at all. Throttling is not optional either: verifying a
    scrypt hash holds 16 MiB and a worker for a moment, which is itself a
    lever worth pulling if nobody is counting.

    The email is stored only as a salted hash, matching how IPs are handled --
    a failed-login table should not become a list of who has an account.
    """

    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    email_hash: Mapped[str] = mapped_column(String(64), index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)


class SystemState(Base):
    """Small key/value store: kill-switch state, corpus version, embedder id."""

    __tablename__ = "system_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WaitlistEntry(Base):
    """Left when a student hits the cap and asks for more. Email is optional."""

    __tablename__ = "waitlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
