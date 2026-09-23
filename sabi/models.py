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
    text,
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
    # Photographs read per day. Its own cap rather than a share of the
    # question allowance: reading a photo is a model call whether or not a
    # question follows it, and a student who takes three blurry pictures of
    # the same page has not asked three questions.
    daily_ocr_cap: Mapped[int] = mapped_column(Integer, default=0)
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


# ===========================================================================
# The exam catalog.
#
# Shape comes from `contracts/question.schema.json`, which is frozen: the
# content pipeline, the API and the web app all build against it, so a column
# here that disagrees with it is a bug in one of the three.
#
# The rule that governs every read of this catalog: **a question is servable
# only when `status == 'verified'` and `licence != 'dev_only'`.** That is
# enforced in the query layer rather than left to callers, because the failure
# it prevents -- an unreviewed or unlicensed question shown to a student -- is
# silent, and a caller who forgets produces no error at all.
# ===========================================================================


class Subject(Base):
    """A subject in the catalog, seeded from contracts/subject_codes.yaml.

    A table rather than an enum because `available` changes: a subject exists
    in the catalog long before it has enough verified content to be offered,
    and a student must never be shown a subject that would give them an empty
    practice set.
    """

    __tablename__ = "subjects"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    track: Mapped[str] = mapped_column(String(16), default="any")
    wave: Mapped[int] = mapped_column(Integer, default=2)

    # False until the subject meets its verified-content threshold. The
    # catalog holding a subject is not the same as a student being able to
    # sit it.
    available: Mapped[bool] = mapped_column(Boolean, default=False)
    # False until the subject's name and code have been checked against the
    # exam body's own published syllabus. A wrong name is what a student picks
    # in onboarding, so this is not cosmetic.
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Passage(Base):
    """A comprehension passage several questions hang off.

    Stored once and referenced, so correcting a passage fixes every question
    that uses it rather than leaving copies to drift apart.
    """

    __tablename__ = "passages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    source_label: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Question(Base):
    """One question in the bank.

    Mirrors `contracts/question.schema.json`. The answer key, the licence and
    the whole verification block live here and are **never** returned by a
    student-facing endpoint -- the API's `Question` schema simply has no field
    for them, so there is nothing to forget to strip.
    """

    __tablename__ = "questions"

    # Derived from the question's identity rather than a surrogate, so a
    # re-import of the same question produces the same id and de-duplication
    # and re-review are idempotent.
    id: Mapped[str] = mapped_column(String(120), primary_key=True)

    exam_body: Mapped[str] = mapped_column(String(16), index=True)
    series: Mapped[str | None] = mapped_column(String(16))
    institution: Mapped[str | None] = mapped_column(String(160))

    subject_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("subjects.code"), index=True
    )
    year: Mapped[int] = mapped_column(Integer, index=True)
    paper: Mapped[str] = mapped_column(String(8), default="1")
    question_number: Mapped[int] = mapped_column(Integer)

    type: Mapped[str] = mapped_column(String(16), default="objective")
    stem: Mapped[str] = mapped_column(Text)
    passage_id: Mapped[int | None] = mapped_column(
        ForeignKey("passages.id", ondelete="SET NULL")
    )
    # [{kind, path, alt}]. `alt` is required by the contract: a diagram with
    # no alternative text is unusable to a screen reader.
    assets: Mapped[list] = mapped_column(JSONB, default=list)

    # [{label, text, why_wrong}]. The count comes from the paper's format
    # config, never assumed to be four -- NECO objective papers use five.
    options: Mapped[list] = mapped_column(JSONB, default=list)

    # {key} | {value, value_kind} | {model_answer, marking_guide, max_marks}
    answer: Mapped[dict] = mapped_column(JSONB, default=dict)

    # {text, locators, author}. An explanation with no locator is not shown.
    explanation: Mapped[dict] = mapped_column(JSONB, default=dict)

    topic: Mapped[str | None] = mapped_column(String(120), index=True)
    subtopic: Mapped[str | None] = mapped_column(String(160))
    difficulty: Mapped[str | None] = mapped_column(String(8))

    # {source, source_detail, source_url, retrieved_on, drafted_by}
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict)

    # The two fields that decide whether a student may ever see this.
    licence: Mapped[str] = mapped_column(String(20), default="original", index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)

    # {answer_check, reviewer, reviewed_on, reviewer_action, reviewer_note,
    #  duplicate_of}
    verification: Mapped[dict] = mapped_column(JSONB, default=dict)

    # For de-duplication. The hash catches an exact re-import; the embedding
    # catches the same question reworded, which is what actually happens when
    # two sources carry one past paper.
    stem_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "exam_body", "year", "subject_code", "paper", "question_number",
            name="uq_question_identity",
        ),
        # The index every student-facing read goes through: servable questions
        # for one subject, narrowed by year or topic.
        Index(
            "ix_questions_servable",
            "subject_code", "exam_body", "year",
            postgresql_where=text("status = 'verified' AND licence <> 'dev_only'"),
        ),
        Index("ix_questions_review_queue", "status", "created_at"),
    )


# ===========================================================================
# The student's own answers to onboarding, and their exam sittings.
# ===========================================================================


class StudentProfile(Base):
    """What onboarding asked, and what the dashboard is built from.

    One row per user, all of it volunteered and all of it editable later. Two
    students with different answers should feel like they are using different
    apps, which only works if these answers actually reach the dashboard, the
    recommendations and the tutor's default subject.
    """

    __tablename__ = "student_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    school_class: Mapped[str | None] = mapped_column(String(8))   # SS1 | SS2 | SS3
    track: Mapped[str | None] = mapped_column(String(16))         # science | commercial | arts | undecided

    # [{exam_body, series, institution}] -- the exams they are preparing for.
    exams: Mapped[list] = mapped_column(JSONB, default=list)
    # {"<exam_body>": ["MTH", "PHY", ...]} -- subjects per exam, because the
    # combination rules differ between bodies.
    subjects: Mapped[dict] = mapped_column(JSONB, default=dict)
    # {"<exam_body>": "2027-04-15"} -- or absent, which is allowed: "I don't
    # know yet" shows the usual window for that exam instead.
    exam_dates: Mapped[dict] = mapped_column(JSONB, default=dict)

    target: Mapped[str | None] = mapped_column(String(120))        # "JAMB 280+"
    weak_topics: Mapped[list] = mapped_column(JSONB, default=list)
    daily_minutes: Mapped[int | None] = mapped_column(Integer)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ExamSession(Base):
    """One timed sitting.

    `started_at` and `seconds_allowed` are the clock, and they live here
    because the server owns the clock. A client that changes the device time
    changes nothing: every response recomputes the remaining seconds from
    these two columns.

    `submitted_at` is the gate on marking. Nothing in a session is marked
    before it is set, which is what separates exam mode from practice.
    """

    __tablename__ = "exam_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Which config drove this sitting, and the copy of it that was used. The
    # copy matters: a format re-verified next season must not silently change
    # how a sitting from last season is scored or reviewed.
    format_key: Mapped[str] = mapped_column(String(64))
    format_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    seconds_allowed: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    score: Mapped[float | None] = mapped_column(Float)
    scale_max: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_exam_sessions_user_started", "user_id", "started_at"),)


class ExamSessionItem(Base):
    """One question as it appeared in one sitting.

    The question is referenced, not copied, but its position and section are
    fixed here so a sitting can be replayed exactly even after the bank moves.
    """

    __tablename__ = "exam_session_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("questions.id", ondelete="RESTRICT")
    )
    section_key: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("session_id", "position", name="uq_exam_item_position"),
    )


class ExamAnswer(Base):
    """What the student put, and when they last changed it.

    `client_seq` is the whole reason this is not a simple upsert. An offline
    client queues answers and replays them on reconnection, and the queue can
    arrive out of order -- so the server keeps the HIGHEST sequence per
    question and ignores anything lower. Last-write-wins would silently
    overwrite the answer a student changed after coming back online with the
    stale one that was still sitting in the queue.
    """

    __tablename__ = "exam_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("exam_session_items.id", ondelete="CASCADE")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="CASCADE"), index=True
    )

    selected_label: Mapped[str | None] = mapped_column(String(1))
    value: Mapped[str | None] = mapped_column(String(255))
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)

    client_seq: Mapped[int] = mapped_column(Integer, default=0)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Written only at submission. Null while the sitting is open, which is
    # what makes "nothing is marked before submit" a property of the data
    # rather than a promise made by a route.
    correct: Mapped[bool | None] = mapped_column(Boolean)

    __table_args__ = (
        UniqueConstraint("item_id", name="uq_exam_answer_item"),
    )


class OcrUpload(Base):
    """What a photograph was read as. Never the photograph.

    There is no `data` column and there must never be one. A photo of an
    exercise book carries a student's name, their handwriting and often their
    school's stamp, and this audience is majority under 18. The hash is
    enough to serve a re-upload from cache, and it cannot be turned back into
    a picture.

    Not scoped to a user on purpose: two students photographing the same
    printed past paper produce the same bytes and the same hash, and the
    second one should not pay for a model call to be told what the first was
    told. The row holds no personal data, so sharing it leaks nothing --
    which is only true *because* the image is discarded.
    """

    __tablename__ = "ocr_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    media_type: Mapped[str] = mapped_column(String(32))
    byte_length: Mapped[int] = mapped_column(Integer, default=0)

    transcription: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str | None] = mapped_column(String(80))
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PracticeSet(Base):
    """One sitting of practice: the questions, and how it went.

    The plan for this feature listed `practice_sets` and `practice_attempts`
    as separate tables, on the assumption that a set is a fixed paper several
    students could sit. That is not how these are built -- every set is
    sampled fresh for one student, from `sabi/practice/templates.py` -- so a
    set and an attempt at it are the same row, and splitting them would mean
    a second table always holding exactly one row per first. Recorded here
    rather than in a commit message, because the plan says otherwise.

    `seconds_allowed` is what makes it timed practice. It is not enforced by
    refusing a late answer: a student who loses their connection halfway
    through has not cheated, and locking them out would be punishing the
    wrong thing. The elapsed time is recorded and shown.
    """

    __tablename__ = "practice_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subject: Mapped[str] = mapped_column(String(64), default="Mathematics")
    exam_board: Mapped[str] = mapped_column(String(32), default="WAEC")
    # Null for a mixed set spanning the whole syllabus.
    topic: Mapped[str | None] = mapped_column(String(120))
    # How the set was put together: mixed | topic | weak
    built_from: Mapped[str] = mapped_column(String(16), default="mixed")

    seconds_allowed: Mapped[int] = mapped_column(Integer, default=900)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_practice_sets_user_created", "user_id", "created_at"),
    )


class PracticeItem(Base):
    """One generated question.

    `template_id` and `params` are the question: the text is re-rendered from
    them rather than trusted from storage, so a row cannot drift out of step
    with the code that marks it. The rendered text is stored anyway, because
    a template that is later removed or corrected must not silently change
    the question a student already answered -- the same reasoning as the
    notebook snapshot.

    `source_doc_id` and `source_locator` point back at the worked example the
    template was drawn from, so a student who gets one wrong is sent to a
    real passage in the corpus rather than to generated prose.
    """

    __tablename__ = "practice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    set_id: Mapped[int] = mapped_column(
        ForeignKey("practice_sets.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    template_id: Mapped[str] = mapped_column(String(64), index=True)
    source_doc_id: Mapped[str] = mapped_column(String(120))
    source_locator: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict] = mapped_column(JSONB, default=dict)

    topic: Mapped[str] = mapped_column(String(120), default="")
    subtopic: Mapped[str] = mapped_column(String(120), default="", index=True)

    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(String(255))
    answer_kind: Mapped[str] = mapped_column(String(16), default="number")
    hint: Mapped[str] = mapped_column(Text, default="")
    working: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint("set_id", "position", name="uq_practice_item_position"),
    )


class PracticeResponse(Base):
    """What a student answered, and whether it was right.

    `user_id` is denormalised off the set so that weak-topic detection is one
    indexed read rather than a join through two tables on every dashboard
    load.
    """

    __tablename__ = "practice_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("practice_items.id", ondelete="CASCADE"), index=True
    )
    set_id: Mapped[int] = mapped_column(
        ForeignKey("practice_sets.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    subject: Mapped[str] = mapped_column(String(64), default="Mathematics")
    subtopic: Mapped[str] = mapped_column(String(120), default="")

    given: Mapped[str] = mapped_column(String(255), default="")
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        # One answer per question. Changing an answer updates the row rather
        # than adding one, or a student could raise their own correct-rate by
        # resubmitting until it passed.
        UniqueConstraint("item_id", name="uq_practice_response_item"),
        Index("ix_practice_responses_user_topic", "user_id", "subtopic", "answered_at"),
    )


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
