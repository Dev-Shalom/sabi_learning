"""Reranking and the retrieval confidence signal.

Two rerankers behind one interface:

* `FeatureReranker` (default) -- deterministic, no network. It scores a
  candidate on idf-weighted term coverage, bigram hits, heading match and term
  density. It is not a cross-encoder and does not pretend to be; it exists so
  that the whole pipeline, and therefore the eval harness, runs offline and
  reproducibly.
* `VoyageReranker` -- rerank-2.5-lite, the production path, used when a key is
  configured. Same interface, so switching it on is a config change and its
  effect is measured by re-running the eval suite rather than assumed.

Confidence is computed here too, because it is a property of the reranked list
rather than of any one chunk. It drives two decisions -- refuse, and escalate to
a stronger model -- so it has to be a single comparable number. The weights were
chosen by hand and the thresholds were then tuned against the golden set; see
EVALUATION.md.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass

from sabi.config import settings
from sabi.retrieval.embeddings import tokenize
from sabi.retrieval.store import Candidate


@dataclass
class Scored:
    candidate: Candidate
    score: float
    features: dict[str, float]


class Reranker(ABC):
    name: str

    @abstractmethod
    def rerank(self, query: str, candidates: list[Candidate]) -> list[Scored]:
        ...


class FeatureReranker(Reranker):
    name = "feature-v1"

    def __init__(self, corpus_df: dict[str, int] | None = None, n_docs: int = 0):
        self.corpus_df = corpus_df or {}
        self.n_docs = n_docs

    def _idf(self, term: str) -> float:
        if not self.n_docs:
            return 1.0
        df = self.corpus_df.get(term, 0)
        return math.log((1 + self.n_docs) / (1 + df)) + 1.0

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Scored]:
        q_terms = tokenize(query)
        if not q_terms:
            return [Scored(c, 0.0, {}) for c in candidates]

        q_unique = list(dict.fromkeys(q_terms))
        q_bigrams = {f"{a} {b}" for a, b in zip(q_terms, q_terms[1:])}
        total_idf = sum(self._idf(t) for t in q_unique) or 1.0

        out: list[Scored] = []
        for c in candidates:
            c_terms = tokenize(c.text)
            c_counts = Counter(c_terms)
            c_set = set(c_terms)
            c_bigrams = {f"{a} {b}" for a, b in zip(c_terms, c_terms[1:])}

            covered_idf = sum(self._idf(t) for t in q_unique if t in c_set)
            coverage = covered_idf / total_idf

            bigram_hits = len(q_bigrams & c_bigrams) / max(1, len(q_bigrams))

            heading_terms = set(tokenize(c.heading or ""))
            heading_hit = (
                len(set(q_unique) & heading_terms) / len(q_unique) if heading_terms else 0.0
            )

            # Density: how concentrated the matched terms are in this chunk.
            matched = sum(c_counts[t] for t in q_unique if t in c_counts)
            density = matched / max(20, len(c_terms))

            score = (
                0.58 * coverage
                + 0.18 * bigram_hits
                + 0.14 * min(1.0, density * 6)
                + 0.10 * heading_hit
            )
            out.append(
                Scored(
                    c,
                    score,
                    {
                        "coverage": round(coverage, 4),
                        "bigram": round(bigram_hits, 4),
                        "density": round(density, 4),
                        "heading": round(heading_hit, 4),
                    },
                )
            )

        out.sort(key=lambda s: s.score, reverse=True)
        return out


class VoyageReranker(Reranker):
    name = "voyage-rerank-2.5-lite"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings().voyage_api_key
        if not self.api_key:
            raise RuntimeError("SABI_VOYAGE_API_KEY is not set but the reranker needs it")

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Scored]:
        import httpx

        if not candidates:
            return []
        r = httpx.post(
            "https://api.voyageai.com/v1/rerank",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "query": query,
                "documents": [c.text for c in candidates],
                "model": "rerank-2.5-lite",
                "top_k": len(candidates),
            },
            timeout=30.0,
        )
        r.raise_for_status()
        results = r.json()["data"]
        return [
            Scored(candidates[item["index"]], float(item["relevance_score"]), {"api": 1.0})
            for item in results
        ]


def confidence(
    scored: list[Scored],
    lexical_refs: set[str],
    semantic_refs: set[str],
) -> tuple[float, dict[str, float]]:
    """A single number in [0, 1] describing how well retrieval did.

    Four signals, because any one of them is easy to fool:

    * `top` -- how good the best chunk looks on its own.
    * `margin` -- how much better it is than the third. A flat list means the
      retriever found a topic but not an answer, which is exactly when the model
      starts inventing.
    * `agreement` -- whether the keyword and vector paths independently found the
      same chunk. Two methods agreeing is worth more than either being confident.
    * `mass` -- whether several chunks support the query, so a one-line fluke
      does not read as certainty.
    """
    if not scored:
        return 0.0, {"top": 0.0, "margin": 0.0, "agreement": 0.0, "mass": 0.0}

    top = scored[0].score
    third = scored[2].score if len(scored) > 2 else 0.0
    margin = max(0.0, top - third)

    top_refs = {s.candidate.ref for s in scored[:3]}
    both = lexical_refs & semantic_refs
    agreement = len(top_refs & both) / 3.0

    mass = sum(1 for s in scored[:4] if s.score >= 0.35 * max(top, 1e-6)) / 4.0

    value = (
        0.50 * min(1.0, top)
        + 0.20 * min(1.0, margin * 2.5)
        + 0.20 * agreement
        + 0.10 * mass
    )
    parts = {
        "top": round(top, 4),
        "margin": round(margin, 4),
        "agreement": round(agreement, 4),
        "mass": round(mass, 4),
    }
    return round(min(1.0, value), 4), parts


def get_reranker(corpus_df: dict[str, int] | None = None, n_docs: int = 0) -> Reranker:
    if settings().voyage_api_key and settings().embedding_provider == "voyage":
        return VoyageReranker()
    return FeatureReranker(corpus_df, n_docs)
