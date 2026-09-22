"""Reading a question off a photograph.

Photo is an **input method**, not part of the grounded answer path. The whole
feature is: read the text, show it to the student in a box they can edit, and
let them press Ask. Nothing is asked automatically, and a transcription never
becomes an answer without a human confirming it first. A model that misreads
"27^(2/3)" as "27^(213)" and is then asked that question without anyone
looking has produced a confidently wrong answer to a question nobody asked --
which is the failure this product exists to prevent, arriving by a new door.

Three rules hold the rest of it together.

**The image bytes are never stored.** A photograph of an exercise book carries
a student's name, their handwriting, their school's stamp, and the audience is
majority under 18. What is kept is a sha256, the media type, the size and the
transcription -- enough to serve the same photo from cache and to answer
"what did it read", and not enough to reconstruct anything. Stated on the
privacy page, not only here.

**The format is decided by the bytes, not by the upload.** `content_type` on a
multipart part is whatever the client typed; a file can claim `image/png` and
be anything at all. `sniff` reads the magic bytes and that is what gets sent.

**It is metered.** `limiter.COUNTED_EVENTS` is the question allowance, and an
event type outside that tuple is free and unlimited -- exactly what
`limiter`'s own docstring forbids. OCR has its own cap on the plan, counted
here, because one photo is a model call whether or not a question follows.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sabi.config import settings
from sabi.limits import limiter
from sabi.llm.base import ImagePart, LLMUnavailable, Transcription, VisionClient
from sabi.models import OcrUpload, Plan, User

# A 12-megapixel phone photo is 3-5 MB. Above that is not a better
# transcription, it is a longer upload on a metered connection.
MAX_BYTES = 5 * 1024 * 1024

# Long enough for a multi-part question, short enough that a runaway
# transcription cannot be pasted into the composer whole.
MAX_TRANSCRIPTION = 2000

# The event type OCR is counted under. Deliberately *not* added to
# `limiter.COUNTED_EVENTS`: a photo must not silently spend a question from
# the daily answering allowance, because the student has not asked anything
# yet and may well discard what comes back.
OCR_EVENT = "ocr"

# Magic bytes, in the order they are tested. Only the formats the vision API
# accepts, so an image that passes here cannot fail later for its format.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


class ImageRejected(ValueError):
    """The upload is not an image this can read. Carries what to tell a student."""


@dataclass
class Read:
    """A transcription, and whether it cost anything to get."""

    text: str
    sha256: str
    media_type: str
    cached: bool
    cost_usd: float = 0.0
    model: str = ""


def sniff(data: bytes) -> str:
    """The media type, from the bytes themselves.

    WEBP needs its own test because the signature is split: `RIFF`, then four
    bytes of length, then `WEBP`.
    """
    for signature, media_type in _SIGNATURES:
        if data.startswith(signature):
            return media_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ImageRejected(
        "That file is not a photo Sabi can read. Send a JPEG, PNG or WEBP "
        "taken with your phone's camera."
    )


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate(data: bytes) -> ImagePart:
    """Size and format, before a byte of it reaches a model."""
    if not data:
        raise ImageRejected("That upload was empty. Try taking the photo again.")
    if len(data) > MAX_BYTES:
        raise ImageRejected(
            f"That photo is {len(data) // (1024 * 1024)} MB, and the limit is "
            f"{MAX_BYTES // (1024 * 1024)} MB. Most phone cameras have a "
            "setting for a smaller picture."
        )
    return ImagePart(data=data, media_type=sniff(data))


# --------------------------------------------------------------- the client


def get_vision() -> VisionClient:
    """Whatever can read an image here, which is usually nothing.

    Mirrors `answer.service.get_llm`, including the shape of the fallback: the
    unavailable client is a real object that raises on use, not None, so every
    caller takes the same path and the failure is a message rather than an
    AttributeError.
    """
    provider = settings().llm_provider
    if provider == "anthropic":
        from sabi.llm.anthropic_client import AnthropicLLM

        return AnthropicLLM()
    if provider == "fixture":
        from sabi.vision.fixtures import FixtureVisionClient

        return FixtureVisionClient()

    from sabi.llm.base import NoVisionClient

    return NoVisionClient()


def vision_model() -> str:
    return settings().vision_model


# --------------------------------------------------------------- the metering


def ocr_today(s: Session, user: User) -> int:
    from sabi.models import UsageEvent

    return int(
        s.execute(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                UsageEvent.user_id == user.id,
                UsageEvent.day == limiter.wat_today(),
                UsageEvent.event_type == OCR_EVENT,
            )
        ).scalar_one()
    )


def ocr_cap(s: Session, user: User) -> int:
    plan = limiter.plan_for(s, user)
    return int(getattr(plan, "daily_ocr_cap", 0) or 0)


def ocr_remaining(s: Session, user: User) -> int:
    return max(0, ocr_cap(s, user) - ocr_today(s, user))


# ------------------------------------------------------------------ the read


def read(
    s: Session,
    *,
    user: User,
    data: bytes,
    client: VisionClient | None = None,
) -> Read:
    """Transcribe an upload, or raise with something worth showing a student.

    Cached on the hash of the bytes, which is worth more here than it looks:
    a student whose connection drops mid-question re-uploads the same
    photograph, and the second attempt should not cost a second model call or
    a second slot from their allowance.
    """
    image = validate(data)
    sha = digest(data)

    cached = s.execute(
        select(OcrUpload).where(OcrUpload.sha256 == sha)
    ).scalar_one_or_none()
    if cached is not None and cached.transcription:
        cached.hits += 1
        return Read(
            text=cached.transcription,
            sha256=sha,
            media_type=cached.media_type,
            cached=True,
            model=cached.model or "",
        )

    if ocr_remaining(s, user) <= 0:
        raise LLMUnavailable(
            "You have used all your photo questions for today. You can still "
            "type a question."
        )

    reader = client or get_vision()
    result: Transcription = reader.transcribe(image, model=vision_model())

    text = " ".join(result.text.split())[:MAX_TRANSCRIPTION]
    if not text:
        raise LLMUnavailable(
            "That photo could not be read. Try again in better light, or type "
            "the question instead."
        )

    # The row records that a photo was read and what it said. `data` is not
    # among the columns and must never be.
    s.add(
        OcrUpload(
            sha256=sha,
            media_type=image.media_type,
            byte_length=len(data),
            transcription=text,
            model=result.model,
            cost_usd=result.cost_usd,
        )
    )
    limiter.record_usage(
        s,
        user,
        None,
        OCR_EVENT,
        result.cost_usd,
        limiter.plan_for(s, user).name,
    )
    s.flush()

    return Read(
        text=text,
        sha256=sha,
        media_type=image.media_type,
        cached=False,
        cost_usd=result.cost_usd,
        model=result.model,
    )
