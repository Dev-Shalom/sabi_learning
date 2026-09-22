"""The LLM interface every provider implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    cost_is_estimated: bool = False
    latency_ms: int = 0
    stop_reason: str | None = None
    meta: dict = field(default_factory=dict)


class LLMClient(ABC):
    provider: str

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int = 700,
        temperature: float | None = None,
    ) -> LLMResponse:
        ...

    def available(self) -> bool:
        return True


class LLMUnavailable(RuntimeError):
    """Raised when the provider cannot serve, so the caller degrades visibly."""


# --------------------------------------------------------------------- vision
#
# Reading a photograph is a second capability, not a second provider. It is a
# separate ABC rather than another method on `LLMClient` because the two are
# independently available: the offline answerer serves every question in this
# deployment and cannot read an image at all, and saying so in the type is
# better than a `complete` that works and a `transcribe` that raises on the
# same object.


@dataclass(frozen=True)
class ImagePart:
    """One image, in memory. The bytes are never persisted -- see sabi/vision."""

    data: bytes
    media_type: str


@dataclass
class Transcription:
    """What a model read off a photograph. Text only: never an answer.

    A transcription is an *input method*. It is shown to the student to
    correct before anything is asked, so this carries no citations, no
    confidence and no claim to be right.
    """

    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    cost_is_estimated: bool = False
    latency_ms: int = 0
    meta: dict = field(default_factory=dict)


class VisionClient(ABC):
    provider: str

    @abstractmethod
    def transcribe(
        self, image: ImagePart, *, model: str, max_tokens: int = 400
    ) -> Transcription:
        ...

    def available(self) -> bool:
        return True


class NoVisionClient(VisionClient):
    """The honest state of this deployment: there is no vision model.

    It raises rather than returning empty text, because empty text would be
    rendered as a transcription the student is invited to correct, and there
    is nothing to correct. The route turns this into a page that says so and
    offers the composer instead, which is the same visible-degradation rule
    `refusals.capacity()` follows when the answering model is unavailable.
    """

    provider = "none"

    def available(self) -> bool:
        return False

    def transcribe(
        self, image: ImagePart, *, model: str, max_tokens: int = 400
    ) -> Transcription:
        raise LLMUnavailable(
            "Sabi cannot read photographs in this deployment. Type the "
            "question instead."
        )
