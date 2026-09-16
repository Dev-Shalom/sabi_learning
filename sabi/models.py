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
from datetime import datetime, timezone

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
    """A device-scoped anonymous identity. No PII is required to use Sabi."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    anon_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    plan: Mapped[str] = mapped_column(
        ForeignKey("plans.name"), default="free", index=True
    )
    # Optional, only if a student volunteers it for the waitlist. Never required.
    email: Mapped[str | None] = mapped_column(String(320))
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

    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    retrieval_ms: Mapped[int] = mapped_column(Integer, default=0)
    generation_ms: Mapped[int] = mapped_column(Integer, default=0)

    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    client: Mapped[str] = mapped_column(String(24), default="web")  # web|eval|cli


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
    expected_refs: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    answerable: Mapped[bool] = mapped_column(Boolean, default=True)
    # Why it is unanswerable, for the failure report: out_of_syllabus |
    # out_of_subject | not_in_corpus | welfare
    unanswerable_kind: Mapped[str | None] = mapped_column(String(40))

    topic: Mapped[str | None] = mapped_column(String(120))
    difficulty: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(Text)
    source_feedback_id: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AnswerCache(Base):
    """Semantic cache. A hit costs one embedding call and a vector lookup."""

    __tablename__ = "answer_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_norm_hash: Mapped[str] = mapped_column(String(64), index=True)
    question: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    payload: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(24))
    corpus_version: Mapped[str] = mapped_column(String(64))

    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
