"""Offline provider: deterministic, extractive, no network, no key.

Why this exists, stated plainly because it matters when reading EVALUATION.md:

The whole system -- retrieval, refusal, caching, cost accounting, the eval
harness, CI -- has to run for someone who clones the repo with no API key. This
provider makes that possible. It does not generate text. It selects sentences
from the retrieved context and stitches them into an answer with citations.

The honest consequence: **groundedness scored against this provider is close to
a tautology**, because every sentence is copied from the context by
construction. Its correctness score is a measure of retrieval quality, not of
model reasoning. EVALUATION.md reports offline and Anthropic numbers in separate
columns and never averages them.

What it does test for real: retrieval, the refusal decision, the citation
contract, the guardrail, caching, metering and cost accounting.
"""

from __future__ import annotations

import re
import time

from sabi.llm.base import LLMClient, LLMResponse
from sabi.llm.pricing import OFFLINE_PRICED_AS, cost_usd
from sabi.retrieval.embeddings import tokenize

SENTENCE_SPLIT = re.compile(r"(?<=[.:;])\s+(?=[A-Z(])")
ANSWER_LINE = re.compile(r"\*\*Answer[^*]*\*\*", re.IGNORECASE)


def _strip_context_header(text: str) -> str:
    """Remove the 'Title - Heading (WAEC Topic, A3)' line the chunker adds."""
    parts = text.split("\n\n", 1)
    return parts[1].strip() if len(parts) == 2 else text.strip()


def _pick_primary(context: list[dict]) -> dict | None:
    """Prefer a Solution over the Question it answers."""
    if not context:
        return None
    best = context[0]
    if (best.get("heading") or "").strip().lower() == "question":
        for c in context:
            if (c.get("heading") or "").strip().lower() == "solution":
                return c
    return best


def _relevant_sentences(body: str, question: str, limit: int = 4) -> list[str]:
    q = set(tokenize(question))
    sentences = [s.strip() for s in SENTENCE_SPLIT.split(body) if s.strip()]
    if not sentences:
        return []
    scored: list[tuple[float, int, str]] = []
    for i, s in enumerate(sentences):
        overlap = len(q & set(tokenize(s)))
        # A small positional bonus: the first sentence of a section usually
        # states the rule, which is what a student asked for.
        scored.append((overlap + (0.5 if i == 0 else 0.0), i, s))

    top = sorted(scored, key=lambda t: (-t[0], t[1]))[:limit]
    chosen = [t for t in top if t[0] > 0] or [scored[0]]
    # Return them in document order: a method read out of order is not a method.
    return [s for _, _, s in sorted(chosen, key=lambda t: t[1])]


class OfflineLLM(LLMClient):
    provider = "offline"

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int = 700,
        temperature: float | None = None,
        context: list[dict] | None = None,
    ) -> LLMResponse:
        started = time.perf_counter()
        context = context or []
        question = user.strip()

        primary = _pick_primary(context)
        paragraphs: list[str] = []
        used_locators: list[str] = []

        if primary is not None:
            body = _strip_context_header(primary["text"])
            locator = primary["locator"]
            heading = (primary.get("heading") or "").lower()

            if "solution" in heading:
                # A method is quoted whole: trimming steps out of a worked
                # solution is exactly the failure the chunker refuses to make.
                paragraphs.append(f"{body}\n\n[{locator}]")
            else:
                picked = _relevant_sentences(body, question)
                paragraphs.append(" ".join(picked) + f" [{locator}]")
            used_locators.append(locator)

            # One supporting citation, and only ever from the syllabus.
            # A second *worked example* is the wrong thing to add: it has
            # different numbers, and pasting "n = 360 / 24 = 15" under an
            # answer about a 12-sided polygon actively misleads. A syllabus
            # extract states the rule, which supports any numbers.
            for c in context:
                if c["locator"] in used_locators:
                    continue
                if c.get("attribution") != "syllabus":
                    continue
                if c.get("score", 0) < 0.3:
                    continue
                extra = _relevant_sentences(_strip_context_header(c["text"]), question, 2)
                if extra:
                    paragraphs.append(" ".join(extra) + f" [{c['locator']}]")
                    used_locators.append(c["locator"])
                break

        text = "\n\n".join(paragraphs).strip()

        # Token counts are estimated from words. They exist so the cost and
        # usage instrumentation has real numbers flowing through it.
        tokens_in = int(len(tokenize(system + user + " ".join(c["text"] for c in context))) * 1.35)
        tokens_out = int(len(tokenize(text)) * 1.35)
        elapsed = int((time.perf_counter() - started) * 1000)

        return LLMResponse(
            text=text,
            model="offline-extractive",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd(OFFLINE_PRICED_AS, tokens_in, tokens_out),
            cost_is_estimated=True,
            latency_ms=elapsed,
            stop_reason="end_turn",
            meta={"priced_as": OFFLINE_PRICED_AS, "locators": used_locators},
        )
