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
from sabi.corpus.ingest import EXCLUSION_HEADING
from sabi.retrieval.embeddings import get_embedder, tokenize
from sabi.retrieval.rerank import Scored, confidence, get_reranker
from sabi.retrieval.scope import DEFAULT_SCOPE, RetrievalScope
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
    # Which syllabus this was retrieved from. Carried on the result so the
    # request row, the refusal copy and the cache key all agree without the
    # caller having to remember to pass it on separately.
    scope: RetrievalScope = DEFAULT_SCOPE

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


# Keyed by (scope, corpus_version): idf is a property of one syllabus, and
# applying Mathematics term frequencies to a Physics question would rank by the
# wrong notion of which words are rare.
_df_state: dict[tuple[str, str], tuple[dict[str, int], int]] = {}


def corpus_document_frequencies(
    s: Session,
    corpus_version: str,
    scope: RetrievalScope = DEFAULT_SCOPE,
) -> tuple[dict[str, int], int]:
    """Term document-frequencies for the reranker's idf, cached per scope."""
    key = (scope.key, corpus_version)
    cached = _df_state.get(key)
    if cached is not None:
        return cached

    from sabi.models import Chunk

    df: Counter[str] = Counter()
    n = 0
    rows = s.execute(
        select(Chunk.text).where(
            Chunk.subject == scope.subject, Chunk.exam_board == scope.exam_board
        )
    ).all()
    for (text_value,) in rows:
        n += 1
        df.update(set(tokenize(text_value)))

    # Bounded: one entry per live scope per corpus version, and a version
    # change is a deploy or an ingest, not a request.
    if len(_df_state) > 32:
        _df_state.clear()
    _df_state[key] = (dict(df), n)
    return _df_state[key]


def retrieve(
    s: Session,
    query: str,
    corpus_version: str = "",
    query_vector: list[float] | None = None,
    scope: RetrievalScope = DEFAULT_SCOPE,
) -> RetrievalResult:
    """Retrieve within exactly one syllabus.

    `scope` defaults, and every parameter stays keyword-compatible, so the CLI,
    the eval harness and every existing test call this unchanged.
    """
    cfg = runtime()
    started = time.perf_counter()

    k_lex = int(cfg.get("retrieval.top_k_lexical", 24))
    k_vec = int(cfg.get("retrieval.top_k_vector", 24))
    rrf_k = int(cfg.get("retrieval.rrf_k", 60))
    rerank_n = int(cfg.get("retrieval.rerank_top_n", 8))
    final_n = int(cfg.get("retrieval.final_context_chunks", 4))

    lexical = _answerable(lexical_candidates(s, query, k_lex, scope=scope))
    # The caller has usually embedded the question already for the cache lookup.
    # Re-embedding here would double the only per-request cost a cache hit has.
    vector = query_vector if query_vector is not None else get_embedder().embed_one(query)
    semantic = _answerable(vector_candidates(s, vector, k_vec, scope=scope))

    fused = reciprocal_rank_fusion([lexical, semantic], k=rrf_k)
    shortlist = _shortlist(fused, lexical, semantic, rerank_n)

    df, n_docs = corpus_document_frequencies(s, corpus_version, scope=scope)
    reranker = get_reranker(df, n_docs)
    scored = reranker.rerank(query, shortlist)

    conf, parts = confidence(
        scored,
        {c.ref for c in lexical},
        {c.ref for c in semantic},
    )

    selected = scored[:final_n]
    selected = _expand_siblings(s, selected, scope=scope)

    elapsed = int((time.perf_counter() - started) * 1000)
    return RetrievalResult(
        query=query,
        scope=scope,
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


# Each retriever's best guesses, guaranteed a hearing. Two rather than one
# because a worked example is usually split across two chunks and the
# question half and the solution half rank adjacently.
GUARANTEED_PER_RETRIEVER = 2


def _answerable(candidates):
    """Drop the 'Not on this syllabus' chunks from answer context.

    An exclusion section says what the syllabus does *not* teach, and the
    refusal path already reads them: `generator.scope_exclusion` runs its own
    query over exactly these chunks, with its own threshold, and builds a
    grounded refusal citing the text and locator. Nothing downstream of here
    needs them.

    Left in, they are actively misleading. Asked "what does a negative index
    mean?", retrieval surfaced the scope document's exclusion list and the
    answer opened "Further Mathematics topics are not examined here" before
    quoting a mean-deviation formula -- a confident non-answer assembled from
    a list of things the paper leaves out.

    Filtered here in Python rather than in the SQL on purpose. Adding
    `AND NOT c.is_exclusion` to the vector query would put a predicate on the
    ANN walk that its partial index does not cover, and the walk would then
    exhaust `ef_search` and quietly return fewer rows than `LIMIT` asked for
    -- the exact failure `sabi/retrieval/scope.py` exists to prevent. The cost
    of filtering afterwards is a couple of the 24 candidate slots.
    """
    return [c for c in candidates if EXCLUSION_HEADING not in (c.heading or "").lower()]


def _shortlist(fused, lexical, semantic, rerank_n: int):
    """The candidates the reranker gets to see.

    Fusion is a cheap heuristic for narrowing the field; the reranker is the
    component that actually judges relevance. Cutting the shortlist at the
    fused ranking alone means fusion's mistakes can never be recovered, and
    reciprocal rank fusion makes a specific mistake here: with `k` at 60 and
    lists only 24 long, every rank contributes between 1/61 and 1/84, so
    appearing in *both* lists outweighs being ranked first in one.

    That is precisely backwards for the case the two retrievers exist to
    cover. "Express a 0.5 mol/dm3 solution of H2SO4 in g/dm3" is answered
    word for word by one worked example. The lexical index misses it -- the
    student wrote "change", the document says "convert" -- while the vector
    search ranks it first and second. Fusion put it twelfth, below the
    shortlist, so the reranker never saw it; asked to rank the full fused
    list, the reranker puts it first. The answer the student got instead was
    a confident explanation of average rate of reaction.

    So each retriever's top few survive regardless of fused rank, and the
    reranker decides. This widens the shortlist by at most four, and the
    reranker is local and lexical, so the cost is nil.
    """
    shortlist = list(fused[:rerank_n])
    seen = {c.ref for c in shortlist}
    for source in (lexical, semantic):
        for candidate in source[:GUARANTEED_PER_RETRIEVER]:
            if candidate.ref not in seen:
                seen.add(candidate.ref)
                shortlist.append(candidate)
    return shortlist


def _expand_siblings(
    s: Session, selected: list[Scored], scope: RetrievalScope = DEFAULT_SCOPE
) -> list[Scored]:
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
    extras = sibling_chunks(s, list(dict.fromkeys(doc_ids)), have, scope=scope)
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
