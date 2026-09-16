"""Turn a source document into retrievable chunks.

Bad chunking is the commonest silent cause of bad retrieval, so the rules here
are explicit and the result is inspectable with `sabi ingest --dry-run`.

The rules:

1. Split on markdown `##` headings first. These documents are already written in
   semantic sections, so heading boundaries beat any fixed window.
2. A section that is too long is split again at paragraph boundaries, never
   mid-paragraph and never mid-sentence.
3. **A worked solution is atomic.** A section whose heading is Solution (or that
   contains numbered solution steps) is never split, whatever its length. Half a
   worked solution retrieved on its own is worse than useless: it looks like a
   complete method and it is not. This single rule is the reason the chunker is
   heading-aware rather than a sliding window.
4. A section that is too short is merged forward into the next one, so that a
   two-line heading stub never becomes a chunk on its own.
5. Every chunk gets a context header naming the document and section. Both the
   embedding and the keyword index see it, which is what lets "what is the
   formula for the sum of interior angles" find a chunk whose body never repeats
   the word "polygon".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sabi.corpus.loader import SourceDocument

# Word counts, not tokens: the corpus is English prose and the ratio is stable
# enough that words are the more legible unit to tune in.
TARGET_WORDS = 180
MAX_WORDS = 340
MIN_WORDS = 40

ATOMIC_HEADINGS = ("solution", "question", "worked example")
NUMBERED_STEP = re.compile(r"^\s*\d+\.\s", re.MULTILINE)


@dataclass
class ChunkDraft:
    index: int
    heading: str | None
    body: str
    atomic: bool = False
    merged_from: int = 1

    @property
    def word_count(self) -> int:
        return len(self.body.split())

    def rendered(self, doc: SourceDocument) -> str:
        """Body with its context header, which is what gets embedded/indexed."""
        bits = [doc.title]
        if self.heading and self.heading.lower() not in doc.title.lower():
            bits.append(self.heading)
        header = " - ".join(bits)
        section = doc.syllabus_section
        tag = f" ({doc.meta.get('exam_board', 'WAEC')} {doc.topic}"
        tag += f", {section})" if section else ")"
        return f"{header}{tag}\n\n{self.body}"


def _split_sections(body: str) -> list[tuple[str | None, str]]:
    """Split markdown into (heading, text) pairs on `##` headings."""
    parts: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    buf: list[str] = []

    for line in body.split("\n"):
        if line.startswith("## "):
            if buf and "".join(buf).strip():
                parts.append((current_heading, "\n".join(buf).strip()))
            current_heading = line[3:].strip()
            buf = []
        else:
            buf.append(line)

    if buf and "".join(buf).strip():
        parts.append((current_heading, "\n".join(buf).strip()))
    return parts


def _is_atomic(heading: str | None, text: str) -> bool:
    if heading and any(h in heading.lower() for h in ATOMIC_HEADINGS):
        return True
    # A block of numbered steps is a method; never cut one in half.
    return len(NUMBERED_STEP.findall(text)) >= 3


def _split_long(text: str) -> list[str]:
    """Split an over-long, non-atomic section at paragraph boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: list[str] = []
    buf: list[str] = []
    count = 0

    for para in paragraphs:
        words = len(para.split())
        if buf and count + words > MAX_WORDS:
            out.append("\n\n".join(buf))
            buf, count = [], 0
        buf.append(para)
        count += words
        if count >= TARGET_WORDS:
            out.append("\n\n".join(buf))
            buf, count = [], 0

    if buf:
        out.append("\n\n".join(buf))
    return out or [text]


def chunk_document(doc: SourceDocument) -> list[ChunkDraft]:
    sections = _split_sections(doc.body)
    drafts: list[ChunkDraft] = []

    for heading, text in sections:
        atomic = _is_atomic(heading, text)
        if atomic or len(text.split()) <= MAX_WORDS:
            drafts.append(ChunkDraft(0, heading, text, atomic=atomic))
        else:
            for piece in _split_long(text):
                drafts.append(ChunkDraft(0, heading, piece, atomic=False))

    # Merge a too-small chunk forward, unless it or its neighbour is atomic --
    # merging into an atomic solution would defeat rule 3.
    merged: list[ChunkDraft] = []
    for draft in drafts:
        if (
            merged
            and not draft.atomic
            and not merged[-1].atomic
            and merged[-1].word_count < MIN_WORDS
        ):
            prev = merged.pop()
            body = f"{prev.body}\n\n{draft.body}"
            heading = prev.heading or draft.heading
            merged.append(
                ChunkDraft(0, heading, body, atomic=False, merged_from=prev.merged_from + 1)
            )
        else:
            merged.append(draft)

    # A trailing stub with nowhere to merge forward goes backwards instead.
    if len(merged) > 1 and merged[-1].word_count < MIN_WORDS and not merged[-1].atomic:
        tail = merged.pop()
        prev = merged.pop()
        merged.append(
            ChunkDraft(
                0,
                prev.heading,
                f"{prev.body}\n\n{tail.body}",
                atomic=prev.atomic,
                merged_from=prev.merged_from + 1,
            )
        )

    for i, d in enumerate(merged):
        d.index = i
    return merged


def chunk_ref(doc_id: str, index: int) -> str:
    return f"{doc_id}#{index}"


@dataclass
class ChunkReport:
    doc_id: str
    locator: str
    chunks: list[ChunkDraft]

    @property
    def warnings(self) -> list[str]:
        out = []
        for c in self.chunks:
            if c.word_count > MAX_WORDS and not c.atomic:
                out.append(f"chunk {c.index} is {c.word_count} words, over the {MAX_WORDS} max")
            if c.word_count < MIN_WORDS and not c.atomic:
                out.append(
                    f"chunk {c.index} is only {c.word_count} words and could not be merged"
                )
        if not self.chunks:
            out.append("document produced no chunks")
        return out


def report(doc: SourceDocument) -> ChunkReport:
    return ChunkReport(doc.doc_id, doc.locator, chunk_document(doc))
