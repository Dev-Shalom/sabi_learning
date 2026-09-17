"""Semantic cache over answers.

Exam questions repeat heavily across students -- that is a structural advantage
of this domain rather than a lucky one, and it is the main cost lever. A hit
costs one embedding call and one vector lookup, with no generation at all.

Correctness constraints that matter more than the hit rate:

* A cache entry is scoped to the corpus version, the prompt version and the
  model. If any of those change, old entries stop matching rather than serving
  an answer produced by a system that no longer exists.
* A refusal is cached too. Refusing fast is as valuable as answering fast, and
  the out-of-syllabus questions repeat just as much as the answerable ones.
* Numbers are what make two maths questions different. "Find the volume of a
  cone of radius 7" and "...of radius 14" are near-identical as text and have
  different answers, so an entry only matches when the multiset of numbers in
  the question matches exactly. This check is cheap and it removes the entire
  class of error that would otherwise make semantic caching unusable here.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from sabi.config import runtime
from sabi.models import AnswerCache

# Bumped by hand whenever the answering code changes in a way that would
# produce a different answer from the same sources. The prompt version does not
# cover this: the offline extractor has no prompt, and a change to citation
# validation or context assembly changes output without touching either the
# prompt or the corpus. A cache that outlives the code that filled it serves
# answers from a system that no longer exists.
ANSWERER_REVISION = "r5"

NUMBER = re.compile(r"\d+(?:\.\d+)?")
WHITESPACE = re.compile(r"\s+")


def normalise(question: str) -> str:
    q = question.strip().lower()
    q = WHITESPACE.sub(" ", q)
    return q.rstrip("?. ")


def scope_key(prompt_version: str, provider: str) -> str:
    """What a cache entry is valid for."""
    return f"{prompt_version}:{provider}:{ANSWERER_REVISION}"


def question_hash(question: str) -> str:
    return hashlib.sha256(normalise(question).encode()).hexdigest()


def number_signature(question: str) -> str:
    """Sorted multiset of the numbers in the question."""
    return ",".join(sorted(NUMBER.findall(question)))


@dataclass
class CacheHit:
    payload: dict[str, Any]
    similarity: float
    entry_id: int
    original_question: str


LOOKUP_SQL = text(
    """
    SELECT id, question, payload, 1 - (embedding <=> CAST(:vec AS vector)) AS sim
    FROM answer_cache
    WHERE prompt_version = :pv
      AND corpus_version = :cv
      AND created_at > :cutoff
      AND embedding IS NOT NULL
    ORDER BY embedding <=> CAST(:vec AS vector)
    LIMIT 5
    """
)


def lookup(
    s: Session,
    question: str,
    vector: list[float],
    prompt_version: str,
    corpus_version: str,
) -> CacheHit | None:
    cfg = runtime()
    if not cfg.get("cache.enabled", True):
        return None

    threshold = float(cfg.get("cache.similarity_threshold", 0.94))
    ttl_days = int(cfg.get("cache.ttl_days", 30))
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
    vec = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"

    rows = s.execute(
        LOOKUP_SQL,
        {"vec": vec, "pv": prompt_version, "cv": corpus_version, "cutoff": cutoff},
    ).all()

    want_numbers = number_signature(question)
    for r in rows:
        if float(r.sim) < threshold:
            break
        if number_signature(r.question) != want_numbers:
            # Same shape, different numbers. Not the same question.
            continue
        return CacheHit(dict(r.payload), float(r.sim), int(r.id), r.question)
    return None


def record_hit(s: Session, entry_id: int) -> None:
    s.execute(
        text(
            "UPDATE answer_cache SET hits = hits + 1, last_hit_at = now() WHERE id = :i"
        ),
        {"i": entry_id},
    )


def store(
    s: Session,
    question: str,
    vector: list[float],
    payload: dict[str, Any],
    model: str,
    prompt_version: str,
    corpus_version: str,
) -> None:
    if not runtime().get("cache.enabled", True):
        return
    s.add(
        AnswerCache(
            question_norm_hash=question_hash(question),
            question=question,
            embedding=[float(x) for x in vector],
            payload=payload,
            model=model,
            prompt_version=prompt_version,
            corpus_version=corpus_version,
        )
    )


def invalidate_all(s: Session) -> int:
    result = s.execute(text("DELETE FROM answer_cache"))
    return int(result.rowcount or 0)
