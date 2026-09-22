"""A vision client backed by committed transcriptions.

There is no API key in this deployment, so the only way the photo path gets
exercised at all is against fixtures. This keys on the sha256 of the image
bytes, so a test drives exactly the same code a student would: the same
validation, the same hashing, the same cache row, the same metering, and only
the model call is substituted.

Deliberately not a heuristic OCR. A hand-rolled reader would be a new
dependency whose mistakes are indistinguishable from a model's mistakes, and
it would make the tests pass against something no student will ever use.
"""

from __future__ import annotations

import json
from pathlib import Path

from sabi.llm.base import ImagePart, LLMUnavailable, Transcription, VisionClient

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "ocr"
INDEX = FIXTURE_DIR / "transcriptions.json"


def _index() -> dict[str, str]:
    if not INDEX.exists():
        return {}
    return json.loads(INDEX.read_text(encoding="utf-8"))


class FixtureVisionClient(VisionClient):
    provider = "fixture"

    def transcribe(
        self, image: ImagePart, *, model: str, max_tokens: int = 400
    ) -> Transcription:
        import hashlib

        sha = hashlib.sha256(image.data).hexdigest()
        text = _index().get(sha)
        if text is None:
            # An unknown image fails the way an unreadable one does, rather
            # than returning something invented. A test that wants a
            # transcription has to commit one.
            raise LLMUnavailable(
                "That photo could not be read. Try again in better light, or "
                "type the question instead."
            )
        return Transcription(
            text=text,
            model=f"fixture:{model}",
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            cost_is_estimated=True,
            latency_ms=0,
        )
