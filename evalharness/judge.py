"""LLM-as-judge, plus a deterministic stand-in.

The rubric lives in `eval/rubric.md` and is loaded verbatim into the prompt, so
a change to grading is a reviewable diff and its hash is recorded in every run.

Two judges:

* `LLMJudge` -- Sonnet 5, one call per item, rubric in the system prompt.
* `HeuristicJudge` -- no model. It maps the deterministic scores onto the same
  shape so the suite produces a complete report with no API key.

The heuristic judge is not pretending to be the real one. Every run records
which judge produced its numbers, the report prints it in the header, and
EVALUATION.md never mixes them. A heuristic "correctness" score is really
"did the expected value appear in the answer", which is a weaker question than
the rubric asks.
"""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sabi.config import runtime, settings

RUBRIC_PATH = Path(__file__).resolve().parent.parent / "eval" / "rubric.md"
JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def rubric_text() -> str:
    return RUBRIC_PATH.read_text(encoding="utf-8")


def rubric_fingerprint() -> str:
    return hashlib.sha256(rubric_text().encode()).hexdigest()[:12]


@dataclass
class Verdict:
    correctness: int | None = None
    groundedness: int | None = None
    student_fit: int | None = None
    refusal_appropriate: bool | None = None
    refusal_quality: int | None = None
    reason: str = ""
    judge: str = "none"
    cost_usd: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Judge(ABC):
    name: str

    @abstractmethod
    def judge(
        self,
        question: str,
        answer: str,
        sources: list[str],
        expected_answer: str | None,
        refused: bool,
        answerable: bool,
    ) -> Verdict:
        ...


class HeuristicJudge(Judge):
    """Deterministic stand-in. Labelled as such everywhere it appears."""

    name = "heuristic"

    def __init__(self, value_passed: bool | None = None, groundedness_ratio: float = 1.0):
        self.value_passed = value_passed
        self.groundedness_ratio = groundedness_ratio

    def judge(
        self,
        question: str,
        answer: str,
        sources: list[str],
        expected_answer: str | None,
        refused: bool,
        answerable: bool,
    ) -> Verdict:
        if refused:
            return Verdict(
                refusal_appropriate=not answerable,
                # Quality proxy: a refusal that offers a next step is worth more
                # than one that stops. It cannot judge tone, so it never gives 2.
                refusal_quality=1 if "Try asking about" in answer else 0,
                reason="heuristic: refusal scored on shape, not wording",
                judge=self.name,
            )

        if self.value_passed is None:
            correctness = None
        else:
            correctness = 2 if self.value_passed else 0

        grounded = 2 if self.groundedness_ratio >= 0.95 else (
            1 if self.groundedness_ratio >= 0.7 else 0
        )
        return Verdict(
            correctness=correctness,
            groundedness=grounded,
            student_fit=None,  # not knowable without a model; never guessed
            reason="heuristic: expected value match and term traceability only",
            judge=self.name,
        )


class LLMJudge(Judge):
    name = "llm"

    def __init__(self, model: str | None = None):
        import anthropic

        key = settings().anthropic_api_key
        if not key:
            raise RuntimeError("the LLM judge needs SABI_ANTHROPIC_API_KEY")
        self.model = model or str(runtime().get("models.judge", "claude-sonnet-5"))
        self._client = anthropic.Anthropic(api_key=key, timeout=60.0)
        self._anthropic = anthropic
        self._rubric = rubric_text()

    def judge(
        self,
        question: str,
        answer: str,
        sources: list[str],
        expected_answer: str | None,
        refused: bool,
        answerable: bool,
    ) -> Verdict:
        source_block = "\n\n".join(f"--- SOURCE\n{s}" for s in sources) or "(no sources)"
        expected = expected_answer or "(none supplied)"
        user = (
            f"QUESTION\n{question}\n\n"
            f"SOURCES GIVEN TO THE SYSTEM\n{source_block}\n\n"
            f"EXPECTED ANSWER\n{expected}\n\n"
            f"THE SYSTEM'S ANSWER\n{answer}"
        )

        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=700,
                system=[
                    {
                        "type": "text",
                        "text": self._rubric,
                        # The rubric is identical on every item, so it caches.
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user}],
                thinking={"type": "adaptive"},
                output_config={"effort": "low"},
            )
        except self._anthropic.APIError as e:
            return Verdict(judge=self.name, error=str(e), reason="judge call failed")

        text = "".join(b.text for b in resp.content if b.type == "text")
        verdict = self._parse(text)

        from sabi.llm.pricing import cost_usd

        usage = resp.usage
        verdict.cost_usd = cost_usd(
            self.model,
            int(getattr(usage, "input_tokens", 0) or 0),
            int(getattr(usage, "output_tokens", 0) or 0),
            int(getattr(usage, "cache_read_input_tokens", 0) or 0),
            int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        )
        return verdict

    def _parse(self, text: str) -> Verdict:
        """Defensive parse.

        The rubric asks for bare JSON. Parsing is done by hand rather than with
        structured outputs so that the judge keeps working if the response comes
        back wrapped in prose -- a judge that throws on its own output format is
        a judge that silently drops items from the report.
        """
        match = JSON_BLOCK.search(text)
        if not match:
            return Verdict(judge=self.name, error="no JSON in judge response", reason=text[:200])
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as e:
            return Verdict(judge=self.name, error=f"bad JSON: {e}", reason=text[:200])

        def as_int(key: str) -> int | None:
            v = data.get(key)
            return int(v) if isinstance(v, (int, float)) else None

        return Verdict(
            correctness=as_int("correctness"),
            groundedness=as_int("groundedness"),
            student_fit=as_int("student_fit"),
            refusal_appropriate=(
                bool(data["refusal_appropriate"])
                if data.get("refusal_appropriate") is not None
                else None
            ),
            refusal_quality=as_int("refusal_quality"),
            reason=str(data.get("reason", ""))[:400],
            judge=self.name,
        )


def get_judge(prefer_llm: bool = True) -> Judge:
    if prefer_llm and settings().anthropic_api_key:
        return LLMJudge()
    return HeuristicJudge()
