"""Model routing.

Cheap model by default. Escalate only when there is a reason to, and record the
reason so the choice can be audited later against cost and quality.

Two reasons to escalate:

* Retrieval confidence sits in the awkward band -- good enough not to refuse,
  not good enough to trust a small model to stay inside the sources.
* The question is structurally complex: several parts, or a long multi-step
  word problem. These are the Paper 2 Section B questions, where a cheap model
  tends to answer part (a) and quietly forget part (b).

Budget pressure overrides both: past the warn fraction, nothing escalates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sabi.config import runtime

MULTIPART = re.compile(r"\(\s*[a-d]\s*\)")


@dataclass(frozen=True)
class RoutingDecision:
    model: str
    escalated: bool
    reason: str


def complexity_score(question: str) -> float:
    """0 to 1. Cheap, deterministic, no model call."""
    words = question.split()
    parts = len(set(MULTIPART.findall(question.lower())))
    score = 0.0
    if parts >= 2:
        score += 0.5
    if len(words) > 45:
        score += 0.3
    elif len(words) > 28:
        score += 0.15
    # "hence", "and hence find", "deduce" mark a question that builds on its
    # own earlier result -- the shape a small model most often drops.
    if re.search(r"\bhence\b|\bdeduce\b|\bshow that\b", question, re.IGNORECASE):
        score += 0.2
    return min(1.0, score)


def choose_model(
    question: str, confidence: float, budget_pressure: bool = False
) -> RoutingDecision:
    cfg = runtime()
    cheap = str(cfg.get("models.default", "claude-haiku-4-5"))
    strong = str(cfg.get("models.escalation", "claude-sonnet-5"))

    if budget_pressure:
        return RoutingDecision(cheap, False, "budget_pressure")

    if confidence < cfg.escalation_threshold:
        return RoutingDecision(strong, True, "low_retrieval_confidence")

    score = complexity_score(question)
    if score >= 0.5:
        return RoutingDecision(strong, True, f"complex_question:{score:.2f}")

    return RoutingDecision(cheap, False, "default")
