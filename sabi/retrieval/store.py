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

from sqlalchemy import text
from sqlalchemy.orm import Session

from sabi.retrieval.embeddings import tokenize


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


LEXICAL_SQL = text(
    """
    SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text, c.provenance,
           ts_rank_cd(c.tsv, query, 32) AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    CROSS JOIN to_tsquery('english', :q) AS query
    WHERE d.active AND c.tsv @@ query
    ORDER BY score DESC
    LIMIT :lim
    """
)

TRIGRAM_SQL = text(
    """
    SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text, c.provenance,
           similarity(c.text, :raw) AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE d.active AND c.text %% :raw
    ORDER BY score DESC
    LIMIT :lim
    """
)

VECTOR_SQL = text(
    """
    SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text, c.provenance,
           1 - (c.embedding <=> CAST(:vec AS vector)) AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE d.active AND c.embedding IS NOT NULL
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


def lexical_candidates(s: Session, query: str, limit: int = 24) -> list[Candidate]:
    q = _tsquery_terms(query)
    rows: list[Any] = []
    if q:
        rows = s.execute(LEXICAL_SQL, {"q": q, "lim": limit}).all()
    if rows:
        return _rows_to_candidates(rows, "lexical")

    # Nothing matched the dictionary: fall back to fuzzy string similarity so a
    # query made entirely of symbols still produces candidates.
    rows = s.execute(TRIGRAM_SQL, {"raw": query, "lim": limit}).all()
    return _rows_to_candidates(rows, "trigram")


def vector_candidates(s: Session, vector: list[float], limit: int = 24) -> list[Candidate]:
    vec = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
    rows = s.execute(VECTOR_SQL, {"vec": vec, "lim": limit}).all()
    return _rows_to_candidates(rows, "semantic")


def chunk_count(s: Session) -> int:
    return int(s.execute(text("SELECT count(*) FROM chunks")).scalar_one())


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


SIBLINGS_SQL = text(
    """
    SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text, c.provenance,
           0.0 AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE d.active AND d.doc_id = ANY(:doc_ids) AND NOT (c.ref = ANY(:exclude))
    ORDER BY d.doc_id, c.chunk_index
    """
)


def sibling_chunks(
    s: Session, doc_ids: list[str], exclude_refs: list[str]
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
        SIBLINGS_SQL, {"doc_ids": doc_ids, "exclude": exclude_refs or [""]}
    ).all()
    return _rows_to_candidates(rows, "sibling")


EXCLUSION_SQL = text(
    """
    SELECT c.id, c.ref, d.doc_id, c.locator, c.heading, c.text, c.provenance,
           0.0 AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE d.active AND c.heading ILIKE :pattern
    """
)


def exclusion_chunks(s: Session, pattern: str = "%not on this syllabus%") -> list[Candidate]:
    """Chunks that say what the syllabus does NOT cover.

    Every syllabus document ends with a section naming what belongs to Further
    Mathematics instead. Indexing those makes a refusal *grounded*: the system
    can cite the line that says differentiating sin x is not on this paper,
    rather than refusing because a similarity score fell below a number.
    """
    rows = s.execute(EXCLUSION_SQL, {"pattern": pattern}).all()
    return _rows_to_candidates(rows, "exclusion")
