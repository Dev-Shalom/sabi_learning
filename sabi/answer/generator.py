"""Deciding whether to answer, and producing the answer if so.

The decision order is deliberate. Cheapest and most certain checks first, model
call last:

1. Grounded out-of-scope. If the syllabus text itself says the topic belongs to
   Further Mathematics, refuse and cite that line. This is the only refusal that
   can point at evidence, so it is tried first.
2. Nothing retrieved at all.
3. Retrieval confidence below the tuned threshold.
4. Otherwise generate -- then validate the citations before showing anything.

Step 4's validation is the part that makes the product's claim true. A citation
the model invented is stripped; if nothing valid survives, the answer is thrown
away and replaced with a refusal. It is better to show a student nothing than to
show them a claim with a fabricated source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from sabi.answer import refusals
from sabi.answer.prompts import get_prompts, render_sources
from sabi.config import runtime
from sabi.llm.base import LLMClient, LLMResponse, LLMUnavailable
from sabi.retrieval.pipeline import RetrievalResult
from sabi.retrieval.store import exclusion_match

CITATION = re.compile(r"\[([A-Z]{2,3}\s?[A-Z]?\d{1,3}(?:\.\d+)?)\]")


@dataclass
class Generated:
    text: str
    refused: bool
    refusal_kind: str | None
    cited_locators: list[str]
    invalid_citations: list[str] = field(default_factory=list)
    evidence_locator: str | None = None
    llm: LLMResponse | None = None
    suggestions: list[str] = field(default_factory=list)


def extract_citations(text: str) -> list[str]:
    return CITATION.findall(text)


def validate_citations(text: str, allowed: set[str]) -> tuple[str, list[str], list[str]]:
    """Strip citations that were not in the sources.

    Returns (cleaned_text, valid_locators, invalid_locators).
    """
    found = extract_citations(text)
    invalid = [c for c in found if c not in allowed]
    cleaned = text
    for bad in set(invalid):
        # Remove the bracket and any space left in front of it, then tidy the
        # spacing before punctuation so the sentence still reads correctly.
        cleaned = cleaned.replace(f" [{bad}]", "").replace(f"[{bad}]", "")
    cleaned = re.sub(r"[ \t]+([.,;:])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    valid = [c for c in extract_citations(cleaned) if c in allowed]
    return cleaned.strip(), list(dict.fromkeys(valid)), sorted(set(invalid))


def suggestions_from(retrieval: RetrievalResult, limit: int = 2) -> list[str]:
    """Two specific things to search next, taken from what was actually found."""
    out: list[str] = []
    for sc in retrieval.chunks:
        prov = sc.candidate.provenance
        label = prov.get("subtopic") or prov.get("topic")
        if label and label.lower() not in [o.lower() for o in out]:
            out.append(label)
        if len(out) >= limit:
            break
    return out


def scope_exclusion(
    s: Session, question: str, query_vector: list[float] | None
) -> tuple[float, object | None]:
    """Score the question against the 'Not on this syllabus' sections."""
    if query_vector is None:
        from sabi.retrieval.embeddings import get_embedder

        query_vector = get_embedder().embed_one(question)

    candidates = exclusion_match(s, question, query_vector)
    if not candidates:
        return 0.0, None
    return candidates[0].score, candidates[0]


def generate(
    s: Session,
    question: str,
    retrieval: RetrievalResult,
    llm: LLMClient,
    model: str,
    query_vector: list[float] | None = None,
) -> Generated:
    cfg = runtime()
    prompts = get_prompts(cfg.prompt_version)
    suggestions = suggestions_from(retrieval)

    # 1. Grounded out-of-scope.
    scope_threshold = float(cfg.get("retrieval.scope_exclusion_threshold", 0.42))
    exc_score, exc_chunk = scope_exclusion(s, question, query_vector)
    # An earlier version also required the exclusion evidence to outscore the
    # best in-scope chunk. That guard never fired: an out-of-syllabus question
    # shares most of its vocabulary with in-scope material ("integration by
    # parts" looks a lot like "integration"), so the in-scope chunk always won.
    # The threshold alone decides, and it is tuned against the golden set with
    # over-refusal on the 78 answerable items as the constraint.
    if exc_chunk is not None and exc_score >= scope_threshold:
        prov = exc_chunk.provenance
        r = refusals.out_of_syllabus(
            prov.get("subtopic") or prov.get("topic"),
            exc_chunk.text,
            exc_chunk.locator,
            suggestions,
        )
        return Generated(r.text, True, r.kind, [], evidence_locator=exc_chunk.locator,
                         suggestions=suggestions)

    # 2. Nothing retrieved.
    if not retrieval.chunks:
        r = refusals.no_material(suggestions)
        return Generated(r.text, True, r.kind, [], suggestions=suggestions)

    # 3. Below the tuned confidence threshold.
    if retrieval.confidence < cfg.refusal_threshold:
        r = refusals.low_confidence(suggestions)
        return Generated(r.text, True, r.kind, [], suggestions=suggestions)

    # 4. Generate, then validate.
    context = retrieval.as_context()
    allowed = {c["locator"] for c in context}
    user = prompts.user_template.format(
        sources=render_sources(context, prompts), question=question
    )

    try:
        response = llm.complete(
            system=prompts.system,
            user=user,
            model=model,
            max_tokens=int(cfg.get("answering.max_answer_tokens", 700)),
            context=context,
        )
    except LLMUnavailable:
        raise

    cleaned, valid, invalid = validate_citations(response.text, allowed)

    if not valid or not cleaned:
        r = refusals.ungrounded(suggestions)
        return Generated(
            r.text, True, r.kind, [], invalid_citations=invalid, llm=response,
            suggestions=suggestions,
        )

    return Generated(
        cleaned, False, None, valid, invalid_citations=invalid, llm=response,
        suggestions=suggestions,
    )
