"""Ingestion pipeline: document in, chunked, embedded, indexed.

Properties that matter:

* **Dry run.** `plan_ingest` returns exactly what would be written, including
  every chunk body, so bad chunking is visible before it is committed.
* **Clean replace.** Re-ingesting a document deletes its chunks and writes new
  ones in one transaction. Re-running ingest never duplicates.
* **No silent index drift.** The embedder identity is recorded in system_state.
  If the configured embedder does not match what the stored vectors were built
  with, ingest refuses and tells you to reindex, rather than writing vectors
  that are not comparable to the ones already there.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from sabi.config import settings
from sabi.corpus.chunker import ChunkDraft, chunk_document, chunk_ref
from sabi.corpus.loader import SourceDocument, load_dir, load_file
from sabi.db import session_scope
from sabi.models import Chunk, Document, SystemState
from sabi.retrieval.embeddings import LocalLSAEmbedder, get_embedder

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent / "corpus"
EMBEDDER_KEY = "embedder"
CORPUS_KEY = "corpus"


@dataclass
class DocumentPlan:
    doc: SourceDocument
    chunks: list[ChunkDraft]
    action: str  # create | replace | unchanged
    warnings: list[str] = field(default_factory=list)

    @property
    def word_counts(self) -> list[int]:
        return [c.word_count for c in self.chunks]


@dataclass
class IngestPlan:
    documents: list[DocumentPlan]
    removed_doc_ids: list[str] = field(default_factory=list)

    @property
    def total_chunks(self) -> int:
        return sum(len(d.chunks) for d in self.documents)

    @property
    def warnings(self) -> list[str]:
        out = []
        for d in self.documents:
            out.extend(f"{d.doc.doc_id}: {w}" for w in d.warnings)
        return out


# The section heading that marks what a syllabus does NOT cover. A corpus-wide
# convention: without such a section a subject has no grounded refusals at all,
# only a confidence threshold. Named here rather than repeated as a default
# argument in two query helpers, which is where it used to live.
EXCLUSION_HEADING = "not on this syllabus"


def _corpus_version(doc_hashes: list[str]) -> str:
    return hashlib.sha256("".join(sorted(doc_hashes)).encode()).hexdigest()[:16]


def configured_only(docs: list[SourceDocument]) -> list[SourceDocument]:
    """Drop documents belonging to a syllabus that is not switched on.

    A subject is authored in `corpus/` long before it is ready to answer
    anybody. Without this filter the loader's `rglob` sweeps those drafts
    into the index the next time anyone runs `sabi ingest` -- which is
    exactly what happened with a half-written Physics corpus: seven
    documents landed in the live index, changed the global corpus version
    and so invalidated the answer cache, while being unreachable because
    `config/limits.yaml` had not declared the subject.

    Turning a subject on is one line of configuration. Until that line
    exists, its documents are drafts and ingest leaves them alone.
    """
    from sabi.retrieval.scope import declared_boards, declared_subjects

    subjects = set(declared_subjects())
    boards = set(declared_boards())
    keep: list[SourceDocument] = []
    for d in docs:
        subject = d.meta.get("subject", "Mathematics")
        board = d.meta.get("exam_board", "WAEC")
        if subject in subjects and board in boards:
            keep.append(d)
    return keep


def collect(
    paths: list[Path] | None = None, include_unconfigured: bool = False
) -> list[SourceDocument]:
    """Documents to ingest.

    `include_unconfigured` is for tooling that wants to look at drafts --
    a linter, a word count. The ingest path never sets it.
    """
    if not paths:
        docs = load_dir(CORPUS_ROOT)
    else:
        docs = []
        for p in paths:
            docs.extend(load_dir(p) if p.is_dir() else [load_file(p)])
    return docs if include_unconfigured else configured_only(docs)


def plan_ingest(
    paths: list[Path] | None = None, prune: bool = False
) -> IngestPlan:
    """Work out what ingest would do. No writes, no embedding calls."""
    docs = collect(paths)
    plans: list[DocumentPlan] = []

    with session_scope() as s:
        existing = {
            d.doc_id: (d.content_hash, len(d.chunks))
            for d in s.execute(select(Document)).scalars()
        }

        for doc in docs:
            drafts = chunk_document(doc)
            warnings: list[str] = []
            for c in drafts:
                if c.word_count < 40 and not c.atomic:
                    warnings.append(f"chunk {c.index} is only {c.word_count} words")
                if c.word_count > 340 and not c.atomic:
                    warnings.append(
                        f"chunk {c.index} is {c.word_count} words, over the soft max"
                    )
            if not drafts:
                warnings.append("produced no chunks")

            prior = existing.get(doc.doc_id)
            if prior is None:
                action = "create"
            elif prior[0] == doc.content_hash:
                action = "unchanged"
            else:
                action = "replace"
            plans.append(DocumentPlan(doc, drafts, action, warnings))

        removed = []
        if prune:
            seen = {d.doc_id for d in docs}
            removed = sorted(set(existing) - seen)

    return IngestPlan(plans, removed)


def _require_compatible_embedder(s, embedder_identity: str, allow_change: bool) -> None:
    row = s.get(SystemState, EMBEDDER_KEY)
    if row is None:
        return
    stored = row.value.get("identity")
    if stored and stored != embedder_identity and not allow_change:
        raise RuntimeError(
            f"stored vectors were built with embedder {stored!r} but the configured "
            f"embedder is {embedder_identity!r}. Run `sabi reindex` to rebuild the "
            "whole index; a partial ingest would write vectors that cannot be "
            "compared with the existing ones."
        )


def apply_ingest(
    paths: list[Path] | None = None,
    prune: bool = False,
    refit: bool = False,
) -> dict[str, object]:
    """Ingest for real. Returns a summary."""
    plan = plan_ingest(paths, prune=prune)
    docs = [dp.doc for dp in plan.documents]
    if not docs:
        return {"documents": 0, "chunks": 0, "note": "nothing to ingest"}

    embedder = get_embedder()

    # The local embedder is fitted on the corpus, so a full ingest refits it.
    # A partial ingest reuses the stored model, which is why reindex exists.
    if refit:
        if isinstance(embedder, LocalLSAEmbedder):
            all_docs = collect(None)
            all_texts = [
                c.rendered(d) for d in all_docs for c in chunk_document(d)
            ]
            embedder.fit(all_texts)
            embedder.save()
    elif isinstance(embedder, LocalLSAEmbedder) and embedder.components is None:
        embedder.load_or_raise()

    rendered: list[str] = []
    for dp in plan.documents:
        rendered.extend(c.rendered(dp.doc) for c in dp.chunks)
    vectors = embedder.embed(rendered) if rendered else []

    written_docs = 0
    written_chunks = 0
    cursor = 0

    with session_scope() as s:
        _require_compatible_embedder(s, embedder.identity, allow_change=refit)

        for dp in plan.documents:
            doc = dp.doc
            row = s.execute(
                select(Document).where(Document.doc_id == doc.doc_id)
            ).scalar_one_or_none()

            if row is None:
                row = Document(doc_id=doc.doc_id)
                s.add(row)

            row.title = doc.title
            row.source = doc.source
            row.attribution = doc.attribution
            row.exam_board = doc.meta.get("exam_board", "WAEC")
            row.subject = doc.meta.get("subject", "Mathematics")
            row.level = doc.meta.get("level", "SS3")
            row.topic = doc.topic
            row.subtopic = doc.subtopic
            row.syllabus_section = doc.syllabus_section
            row.year = doc.meta.get("year")
            row.paper = doc.meta.get("paper")
            row.question_no = doc.meta.get("question_no")
            row.locator = doc.locator
            row.body = doc.body
            row.content_hash = doc.content_hash
            row.source_path = str(doc.path)
            row.active = True
            row.updated_at = datetime.now(timezone.utc)
            s.flush()

            # Clean replace: the old chunks go, the new ones land, one txn.
            s.execute(delete(Chunk).where(Chunk.document_id == row.id))

            provenance = doc.provenance()
            for c in dp.chunks:
                vec = vectors[cursor]
                cursor += 1
                s.add(
                    Chunk(
                        document_id=row.id,
                        chunk_index=c.index,
                        ref=chunk_ref(doc.doc_id, c.index),
                        heading=c.heading,
                        text=c.rendered(doc),
                        token_estimate=int(c.word_count * 1.3),
                        locator=doc.locator,
                        # Denormalised onto the chunk so retrieval can be
                        # scoped without a join. Taken from the row just
                        # written, so the two can never disagree.
                        subject=row.subject,
                        exam_board=row.exam_board,
                        is_exclusion=EXCLUSION_HEADING in (c.heading or "").lower(),
                        provenance=provenance | {"heading": c.heading, "atomic": c.atomic},
                        embedding=[float(x) for x in vec],
                        embedding_model=embedder.identity,
                    )
                )
                written_chunks += 1
            written_docs += 1

        for doc_id in plan.removed_doc_ids:
            s.execute(delete(Document).where(Document.doc_id == doc_id))

        rows = s.execute(
            select(Document.exam_board, Document.subject, Document.content_hash)
        ).all()
        all_hashes = [h for (_, _, h) in rows]
        # The global version stays: the embedder is fitted over the whole
        # corpus, so a change anywhere still invalidates every vector.
        version = _corpus_version(all_hashes)

        # And one version per syllabus, which is what the answer cache keys
        # on. With only a global version, adding one Physics document flushed
        # every cached Mathematics answer -- and the cache is the cost lever.
        by_scope: dict[str, list[str]] = {}
        for board, subject, h in rows:
            by_scope.setdefault(f"{board}:{subject}", []).append(h)
        scopes = {
            key: {"version": _corpus_version(hashes), "documents": len(hashes)}
            for key, hashes in sorted(by_scope.items())
        }

        for key, value in (
            (EMBEDDER_KEY, {"identity": embedder.identity, "provider": settings().embedding_provider}),
            (
                CORPUS_KEY,
                {"version": version, "documents": len(all_hashes), "scopes": scopes},
            ),
        ):
            row = s.get(SystemState, key)
            if row is None:
                s.add(SystemState(key=key, value=value))
            else:
                row.value = value

    return {
        "documents": written_docs,
        "chunks": written_chunks,
        "removed": len(plan.removed_doc_ids),
        "embedder": embedder.identity,
        "corpus_version": version,
        "warnings": plan.warnings,
    }


def reindex() -> dict[str, object]:
    """Refit the embedder on the whole corpus and rewrite every vector."""
    return apply_ingest(None, prune=True, refit=True)


def corpus_version(s: Session | None = None, scope_key: str | None = None) -> str:
    """The corpus version, globally or for one syllabus.

    Pass the session you already have. The request path used to call this with
    no session, which opened a second connection per request against a pool of
    five -- and a second connection is what the request-path deadlock was made
    of. With no session it still works, for the CLI.
    """
    if s is None:
        with session_scope() as own:
            return corpus_version(own, scope_key)

    row = s.get(SystemState, CORPUS_KEY)
    if row is None:
        return "unindexed"

    version = str(row.value.get("version"))
    if scope_key is None:
        return version

    scopes = row.value.get("scopes")
    if not scopes:
        # The row predates per-scope versions: written by an ingest that ran
        # before this existed, and not yet replaced. Fall back to the global
        # version rather than the sentinel below, so that deploying this code
        # does not throw away a warm cache before the next ingest has run.
        return version

    scoped = scopes.get(scope_key)
    # A scope that is configured but has no documents gets a version of its
    # own that nothing else shares, so nothing can be served from the cache
    # for it by accident. That is a different case from the one above: here we
    # know what every scope's version is, and this one's corpus is empty.
    return str(scoped["version"]) if scoped else f"empty:{scope_key}"
