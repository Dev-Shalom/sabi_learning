"""The retrieval pipeline: hybrid recall, RRF fusion, rerank, confidence."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sabi.config import runtime
from sabi.retrieval.embeddings import get_embedder, tokenize
from sabi.retrieval.rerank import Scored, confidence, get_reranker
from sabi.retrieval.store import (
    Candidate,
    lexical_candidates,
    sibling_chunks,
    vector_candidates,
)

# Documents whose sections only make sense together. A syllabus document is a
# reference text and its sections stand alone; a worked example is a question
# and its method, and half of that is a trap.
EXPAND_ATTRIBUTIONS = {"worked_example", "past_question"}
MAX_CONTEXT_CHUNKS = 8


@dataclass
class RetrievalResult:
    query: str
    chunks: list[Scored]
    confidence: float
    confidence_parts: dict[str, float]
    retrieval_ms: int
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def refs(self) -> list[str]:
        return [s.candidate.ref for s in self.chunks]

    def as_context(self) -> list[dict[str, Any]]:
        """What the generator sees. Locator first, so the model cites by locator."""
        return [
            {
                "locator": s.candidate.locator,
                "ref": s.candidate.ref,
                "doc_id": s.candidate.doc_id,
                "heading": s.candidate.heading,
                "attribution": s.candidate.provenance.get("attribution"),
                "source": s.candidate.provenance.get("source"),
                "text": s.candidate.text,
                "score": round(s.score, 4),
            }
            for s in self.chunks
        ]


def reciprocal_rank_fusion(
    lists: list[list[Candidate]], k: int = 60
) -> list[Candidate]:
    """RRF: rank-based, so the two incomparable score scales never meet.

    A chunk found by both paths accumulates from both, which is precisely the
    behaviour we want -- agreement between independent retrievers is evidence.
    """
    scores: dict[str, float] = {}
    best: dict[str, Candidate] = {}
    for candidates in lists:
        for c in candidates:
            scores[c.ref] = scores.get(c.ref, 0.0) + 1.0 / (k + c.rank)
            # Keep whichever copy has the better in-list rank, for its metadata.
            if c.ref not in best or c.rank < best[c.ref].rank:
                best[c.ref] = c

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    out: list[Candidate] = []
    for i, (ref, score) in enumerate(ordered):
        c = best[ref]
        out.append(
            Candidate(
                ref=c.ref,
                chunk_id=c.chunk_id,
                doc_id=c.doc_id,
                locator=c.locator,
                heading=c.heading,
                text=c.text,
                provenance=c.provenance,
                score=score,
                rank=i + 1,
                source=c.source,
            )
        )
    return out


@lru_cache(maxsize=1)
def _df_cache_key() -> int:
    return 0


_df_state: dict[str, Any] = {"df": {}, "n": 0, "loaded_for": None}


def corpus_document_frequencies(s: Session, corpus_version: str) -> tuple[dict[str, int], int]:
    """Term document-frequencies for the reranker's idf, cached per corpus version."""
    if _df_state["loaded_for"] == corpus_version:
        return _df_state["df"], _df_state["n"]

    from sabi.models import Chunk

    df: Counter[str] = Counter()
    n = 0
    for (text_value,) in s.execute(select(Chunk.text)).all():
        n += 1
        df.update(set(tokenize(text_value)))

    _df_state.update({"df": dict(df), "n": n, "loaded_for": corpus_version})
    return _df_state["df"], n


def retrieve(
    s: Session,
    query: str,
    corpus_version: str = "",
    query_vector: list[float] | None = None,
) -> RetrievalResult:
    cfg = runtime()
    started = time.perf_counter()

    k_lex = int(cfg.get("retrieval.top_k_lexical", 24))
    k_vec = int(cfg.get("retrieval.top_k_vector", 24))
    rrf_k = int(cfg.get("retrieval.rrf_k", 60))
    rerank_n = int(cfg.get("retrieval.rerank_top_n", 8))
    final_n = int(cfg.get("retrieval.final_context_chunks", 4))

    lexical = lexical_candidates(s, query, k_lex)
    # The caller has usually embedded the question already for the cache lookup.
    # Re-embedding here would double the only per-request cost a cache hit has.
    vector = query_vector if query_vector is not None else get_embedder().embed_one(query)
    semantic = vector_candidates(s, vector, k_vec)

    fused = reciprocal_rank_fusion([lexical, semantic], k=rrf_k)
    shortlist = fused[:rerank_n]

    df, n_docs = corpus_document_frequencies(s, corpus_version)
    reranker = get_reranker(df, n_docs)
    scored = reranker.rerank(query, shortlist)

    conf, parts = confidence(
        scored,
        {c.ref for c in lexical},
        {c.ref for c in semantic},
    )

    selected = scored[:final_n]
    selected = _expand_siblings(s, selected)

    elapsed = int((time.perf_counter() - started) * 1000)
    return RetrievalResult(
        query=query,
        chunks=selected,
        confidence=conf,
        confidence_parts=parts,
        retrieval_ms=elapsed,
        counts={
            "lexical": len(lexical),
            "semantic": len(semantic),
            "fused": len(fused),
            "reranked": len(scored),
            "final": len(selected),
        },
    )


def _expand_siblings(s: Session, selected: list[Scored]) -> list[Scored]:
    """Pull in the rest of a matched worked example, keeping order sensible."""
    if not selected:
        return selected

    doc_ids = [
        sc.candidate.doc_id
        for sc in selected
        if sc.candidate.provenance.get("attribution") in EXPAND_ATTRIBUTIONS
    ]
    if not doc_ids:
        return selected

    have = [sc.candidate.ref for sc in selected]
    extras = sibling_chunks(s, list(dict.fromkeys(doc_ids)), have)
    if not extras:
        return selected

    by_doc: dict[str, list[Candidate]] = {}
    for c in extras:
        by_doc.setdefault(c.doc_id, []).append(c)

    out: list[Scored] = []
    for sc in selected:
        out.append(sc)
        for c in by_doc.pop(sc.candidate.doc_id, []):
            # An expanded chunk inherits a slightly lower score: it is context,
            # not the thing that matched, and the ordering should say so.
            out.append(Scored(c, sc.score * 0.99, {"expanded": 1.0}))

    return out[:MAX_CONTEXT_CHUNKS]
