"""Candidate generation against Postgres.

Two independent recall paths, deliberately kept separate so that fusion can see
where each candidate came from:

* lexical -- Postgres full-text search with `ts_rank_cd`, falling back to
  trigram similarity when the query has no indexable dictionary terms (this
  happens with things like "n(A)" or "22/7").
* semantic -- pgvector cosine distance over the chunk embeddings.

Everything here returns `Candidate` objects with a rank, because RRF needs the
rank and not the raw score: the two scoring scales are not comparable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.orm import Session

from sabi.retrieval.embeddings import tokenize
from sabi.retrieval.scope import DEFAULT_SCOPE, RetrievalScope


@dataclass
class Candidate:
    ref: str
    chunk_id: int
    doc_id: str
    locator: str
    heading: str | None
    text: str
    provenance: dict[str, Any]
    score: float
    rank: int
    source: str  # lexical | semantic | trigram


def _tsquery_terms(query: str) -> str:
    """OR the content terms together.

    AND semantics (`plainto_tsquery`) is too strict for a student's phrasing --
    "how do I find the sum of interior angles of a 12 sided polygon" shares few
    exact terms with any one chunk. OR plus `ts_rank_cd` ranking gives recall
    without letting a single common word dominate.
    """
    terms = [t for t in tokenize(query) if t.isalnum()]
    return " | ".join(terms[:24])


# Every statement below is built per scope, because the scope predicate has to
# be a literal for a partial index to match it. `sabi/retrieval/scope.py`
# explains why, and guarantees the literal is safe. Statements are cached so
# the string work happens once per scope rather than once per request.


@lru_cache(maxsize=64)
def _lexical_sql(scope: RetrievalScope):
    return text(
        f"""
        SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text, c.provenance,
               ts_rank_cd(c.tsv, query, 32) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        CROSS JOIN to_tsquery('english', :q) AS query
        WHERE d.active AND {scope.predicate('c')} AND c.tsv @@ query
        ORDER BY score DESC
        LIMIT :lim
        """
    )


@lru_cache(maxsize=64)
def _trigram_sql(scope: RetrievalScope):
    return text(
        f"""
        SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text, c.provenance,
               similarity(c.text, :raw) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        -- An explicit threshold rather than the `%` operator: a literal percent
        -- sign does not survive the driver's parameter escaping, and `%` depends
        -- on a session GUC anyway, so spelling the threshold out is both safer
        -- and clearer about what "similar enough" means.
        WHERE d.active AND {scope.predicate('c')} AND similarity(c.text, :raw) > 0.08
        ORDER BY score DESC
        LIMIT :lim
        """
    )


@lru_cache(maxsize=64)
def _vector_sql(scope: RetrievalScope):
    """The one that most needs the partial index.

    `ORDER BY embedding <=> :vec LIMIT n` walks the HNSW graph. With a filter
    the graph cannot satisfy, the walk exhausts `ef_search` and returns fewer
    than `n` rows -- silently. The predicate here matches
    `ix_chunks_hnsw_<scope>`, so the walk only ever visits in-scope nodes.
    """
    return text(
        f"""
        SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text, c.provenance,
               1 - (c.embedding <=> CAST(:vec AS vector)) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.active AND {scope.predicate('c')} AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> CAST(:vec AS vector)
        LIMIT :lim
        """
    )


def _rows_to_candidates(rows, source: str) -> list[Candidate]:
    out: list[Candidate] = []
    for i, r in enumerate(rows):
        out.append(
            Candidate(
                ref=r.ref,
                chunk_id=r.id,
                doc_id=r.doc_id,
                locator=r.locator,
                heading=r.heading,
                text=r.text,
                provenance=r.provenance or {},
                score=float(r.score),
                rank=i + 1,
                source=source,
            )
        )
    return out


def lexical_candidates(
    s: Session,
    query: str,
    limit: int = 24,
    scope: RetrievalScope = DEFAULT_SCOPE,
) -> list[Candidate]:
    q = _tsquery_terms(query)
    rows: list[Any] = []
    if q:
        rows = s.execute(_lexical_sql(scope), {"q": q, "lim": limit}).all()
    if rows:
        return _rows_to_candidates(rows, "lexical")

    # Nothing matched the dictionary: fall back to fuzzy string similarity so a
    # query made entirely of symbols still produces candidates.
    rows = s.execute(_trigram_sql(scope), {"raw": query, "lim": limit}).all()
    return _rows_to_candidates(rows, "trigram")


def vector_candidates(
    s: Session,
    vector: list[float],
    limit: int = 24,
    scope: RetrievalScope = DEFAULT_SCOPE,
) -> list[Candidate]:
    vec = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
    rows = s.execute(_vector_sql(scope), {"vec": vec, "lim": limit}).all()
    return _rows_to_candidates(rows, "semantic")


def chunk_count(s: Session, scope: RetrievalScope | None = None) -> int:
    if scope is None:
        return int(s.execute(text("SELECT count(*) FROM chunks")).scalar_one())
    return int(
        s.execute(
            text(f"SELECT count(*) FROM chunks c WHERE {scope.predicate('c')}")
        ).scalar_one()
    )


def fetch_chunks_by_ref(s: Session, refs: list[str]) -> dict[str, Candidate]:
    if not refs:
        return {}
    rows = s.execute(
        text(
            """
            SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text,
                   c.provenance, 1.0 AS score
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE c.ref = ANY(:refs)
            """
        ),
        {"refs": refs},
    ).all()
    return {c.ref: c for c in _rows_to_candidates(rows, "direct")}


@lru_cache(maxsize=64)
def _siblings_sql(scope: RetrievalScope):
    return text(
        f"""
        SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text, c.provenance,
               0.0 AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.active AND {scope.predicate('c')}
          AND d.doc_id = ANY(:doc_ids) AND NOT (c.ref = ANY(:exclude))
        ORDER BY d.doc_id, c.chunk_index
        """
    )


def sibling_chunks(
    s: Session,
    doc_ids: list[str],
    exclude_refs: list[str],
    scope: RetrievalScope = DEFAULT_SCOPE,
) -> list[Candidate]:
    """Other chunks belonging to documents we already matched.

    A student's question matches the *Question* section of a worked example
    almost word for word, and that section contains no method. Retrieving it
    alone would hand the generator a question and no answer -- so once a
    document is matched, its remaining sections come along. Indexing them
    separately keeps the match sharp; expanding here keeps the context complete.
    """
    if not doc_ids:
        return []
    rows = s.execute(
        _siblings_sql(scope), {"doc_ids": doc_ids, "exclude": exclude_refs or [""]}
    ).all()
    return _rows_to_candidates(rows, "sibling")


# `c.is_exclusion`, set at ingest, replaces an unindexed
# `heading ILIKE '%not on this syllabus%'` over every chunk on every request --
# with the pattern hardcoded as a default argument in two separate functions.
#
# Scoping these is the single highest-risk part of adding a second syllabus.
# "Not on this syllabus" is only meaningful about one syllabus: unscoped, a
# question that Further Maths excludes would be refused even when the Physics
# corpus answers it, and a subject with no exclusion sections of its own would
# borrow another's.


@lru_cache(maxsize=64)
def _exclusion_sql(scope: RetrievalScope):
    return text(
        f"""
        SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text, c.provenance,
               0.0 AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.active AND c.is_exclusion AND {scope.predicate('c')}
        """
    )


@lru_cache(maxsize=64)
def _exclusion_match_sql(scope: RetrievalScope):
    return text(
        f"""
        SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text, c.provenance,
               (0.5 * COALESCE(ts_rank_cd(c.tsv, query, 32), 0)
                + 0.5 * (1 - (c.embedding <=> CAST(:vec AS vector)))) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        LEFT JOIN LATERAL to_tsquery('english', :q) AS query ON true
        WHERE d.active AND c.is_exclusion AND {scope.predicate('c')}
          AND c.embedding IS NOT NULL
        ORDER BY score DESC
        LIMIT :lim
        """
    )


def exclusion_match(
    s: Session,
    query: str,
    vector: list[float],
    limit: int = 3,
    scope: RetrievalScope = DEFAULT_SCOPE,
) -> list[Candidate]:
    """Score a question against the out-of-scope sections, lexically and semantically.

    The first version of this scored lexical term overlap only, and caught
    0 of 12 out-of-syllabus questions in the golden set: the corpus says
    "Differentiation of trigonometric ... functions", the student types
    "Differentiate sin x", and raw token overlap sees two different words.
    Postgres full-text search stems both to the same root, and the vector half
    covers the cases where the wording shares no stem at all ("dot product" vs
    "scalar product"). `ts_rank_cd` with normalisation flag 32 is bounded to
    0..1, so the two halves are on comparable scales before being averaged.
    """
    q = _tsquery_terms(query)
    vec = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
    rows = s.execute(
        _exclusion_match_sql(scope),
        {"q": q or "nothing", "vec": vec, "lim": limit},
    ).all()
    return _rows_to_candidates(rows, "exclusion")


def exclusion_chunks(
    s: Session, scope: RetrievalScope = DEFAULT_SCOPE
) -> list[Candidate]:
    """Chunks that say what the syllabus does NOT cover.

    Every syllabus document ends with a section naming what belongs to Further
    Mathematics instead. Indexing those makes a refusal *grounded*: the system
    can cite the line that says differentiating sin x is not on this paper,
    rather than refusing because a similarity score fell below a number.
    """
    rows = s.execute(_exclusion_sql(scope)).all()
    return _rows_to_candidates(rows, "exclusion")
