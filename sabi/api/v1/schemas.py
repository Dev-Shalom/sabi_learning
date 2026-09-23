"""Response and request bodies for the JSON API.

These mirror `contracts/openapi.yaml`, which is frozen. `openapi-typescript`
generates the front end's types from what FastAPI publishes, so a field that
drifts from the contract breaks a typecheck rather than production.

The one that matters most is `QuestionOut`. It is deliberately not the stored
row: there is no answer key on it, no licence, no verification block, no
provenance source. Not "stripped before sending" -- *absent*, so there is
nothing for a future endpoint to forget to remove.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Problem(BaseModel):
    """An error, written to be shown to a student as-is.

    Plain, specific, never a dead end. A refusal says what it cannot do and
    what it can.
    """

    code: Literal[
        "bad_request", "unauthenticated", "forbidden", "not_found", "conflict",
        "rate_limited", "consent_required", "capacity", "unavailable",
    ]
    message: str
    retry_after_seconds: int | None = None


# ----------------------------------------------------------------- identity


class Allowance(BaseModel):
    """What is left today, per capability.

    Separate counters on purpose: reading a photo is a model call whether or
    not a question follows it, so it must not spend a question the student has
    not asked.
    """

    questions_remaining: int
    questions_cap: int
    tutor_remaining: int
    photos_remaining: int
    exams_remaining: int
    resets_phrase: str


class ViewerOut(BaseModel):
    authenticated: bool
    display_name: str | None = None
    # Under 18. Drives the consent gate; never rendered as a label on anyone.
    is_minor: bool = False
    consent_state: Literal["not_required", "pending", "granted"] = "not_required"
    onboarded: bool = False
    allowance: Allowance


# ------------------------------------------------------------------ catalog


class SubjectOut(BaseModel):
    code: str
    name: str
    track: str
    # False until the subject meets its verified-content threshold. A subject
    # in the catalog is not a subject a student may sit.
    available: bool
    years_available: list[int] = Field(default_factory=list)


class ExamSectionOut(BaseModel):
    key: str
    title: str
    subject: str | None = None
    question_count: int
    question_type: str
    compulsory: bool = False


class ExamFormatOut(BaseModel):
    key: str
    exam_body: str
    exam_name: str
    delivery: str | None = None
    total_duration_minutes: int | None = None
    option_labels: list[str]
    sections: list[ExamSectionOut]
    scale_max: float | None = None
    # Sent as data so the client hard-codes no key bindings. JAMB's come from
    # its own manual; another body's will differ.
    keyboard: dict[str, Any] = Field(default_factory=dict)
    show_attempted_count_on_submit: bool = True
    verified_on: str
    source_url: str


# ---------------------------------------------------------------- questions


class OptionOut(BaseModel):
    label: str
    text: str


class QuestionOut(BaseModel):
    """A question as a student sees it.

    No answer key, no licence, no verification block. Their absence is the
    safety property: an endpoint cannot leak a field this model does not have.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    stem: str
    passage: str | None = None
    options: list[OptionOut] = Field(default_factory=list)
    assets: list[dict[str, Any]] = Field(default_factory=list)
    topic: str | None = None
    source_label: str | None = None


class MarkingOut(BaseModel):
    """Returned only once an answer is committed, and in exam mode only after
    submission."""

    correct: bool
    correct_label: str | None = None
    correct_value: str | None = None
    explanation: str | None = None
    why_wrong: str | None = None
    locators: list[str] = Field(default_factory=list)


class PageOut(BaseModel):
    items: list[Any]
    next_cursor: str | None = None


# ----------------------------------------------------------------- practice


class PracticeSetRequest(BaseModel):
    subject_code: str
    exam_body: str = "WAEC"
    year: int | None = None
    topic: str | None = None
    count: int = Field(default=10, ge=1, le=40)


class PracticeItemOut(BaseModel):
    id: int
    position: int
    question: QuestionOut
    answered: bool = False
    given: str | None = None
    marking: MarkingOut | None = None


class PracticeSetOut(BaseModel):
    id: int
    subject_code: str
    exam_body: str
    created_at: datetime
    items: list[PracticeItemOut]


class PracticeAnswerRequest(BaseModel):
    question_id: str
    selected_label: str | None = None
    value: str | None = None


# --------------------------------------------------------------- exam mode


class ExamStartRequest(BaseModel):
    format_key: str
    # For JAMB the elective subjects a candidate chose; the compulsory section
    # is filled from the format.
    subject_codes: list[str] = Field(default_factory=list)


class ExamAnswerIn(BaseModel):
    """One answer, with the sequence number that makes replay safe.

    `client_seq` is monotonic per session on the client. The server keeps the
    highest per question and ignores anything lower, so an offline queue
    replaying out of order cannot overwrite a newer answer with a stale one.
    """

    question_id: str
    selected_label: str | None = None
    value: str | None = None
    flagged: bool = False
    client_seq: int = 0


class ExamItemOut(BaseModel):
    position: int
    section_key: str
    question: QuestionOut
    selected_label: str | None = None
    value: str | None = None
    flagged: bool = False
    # Null until the sitting is submitted. Marking before then would make a
    # timed exam a guessing game against the marker.
    marking: MarkingOut | None = None


class ExamSessionOut(BaseModel):
    id: str
    format: ExamFormatOut
    # Authoritative, from the server, on every response. The client displays
    # it and never computes it.
    seconds_remaining: int
    state: Literal["active", "submitted", "expired"]
    answered_count: int
    total_count: int
    started_at: datetime
    submitted_at: datetime | None = None
    score: float | None = None
    scale_max: float | None = None
    items: list[ExamItemOut] = Field(default_factory=list)


class ExamResultSection(BaseModel):
    key: str
    title: str
    correct: int
    total: int
    score: float


class ExamResultOut(BaseModel):
    session_id: str
    score: float
    scale_max: float
    correct: int
    total: int
    seconds_taken: int
    sections: list[ExamResultSection]
    weakest_topics: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------- tutor


class TutorAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    subject_code: str
    exam_body: str = "WAEC"


class CitationOut(BaseModel):
    locator: str
    title: str
    attribution: str | None = None
    text: str
    highlight: str | None = None


class TutorAnswerOut(BaseModel):
    text: str
    refused: bool
    refusal_kind: str | None = None
    # An answer with no valid citation is discarded by the server, so this is
    # never empty on a non-refusal. The client cannot render an uncited answer
    # because it is never sent one.
    citations: list[CitationOut] = Field(default_factory=list)
    disclosure: str = ""
    request_id: str | None = None
    confidence: float | None = None


# -------------------------------------------------------------- onboarding


class OnboardingIn(BaseModel):
    school_class: str | None = None
    track: str | None = None
    exams: list[dict[str, Any]] = Field(default_factory=list)
    subjects: dict[str, list[str]] = Field(default_factory=dict)
    exam_dates: dict[str, str] = Field(default_factory=dict)
    target: str | None = None
    weak_topics: list[str] = Field(default_factory=list)
    daily_minutes: int | None = None


class OnboardingOut(OnboardingIn):
    completed: bool = False


# --------------------------------------------------------------- notebook


class NotebookSaveRequest(BaseModel):
    request_id: str | None = None
    question_id: str | None = None
    note: str = ""


class NotebookEntryOut(BaseModel):
    id: int
    question: str
    answer: str
    subject: str
    topic: str | None = None
    note: str | None = None
    created_at: datetime
    citations: list[CitationOut] = Field(default_factory=list)
    disclosure: str = ""
