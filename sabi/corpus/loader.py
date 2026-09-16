"""Read corpus documents off disk.

A corpus document is a markdown file with a YAML front-matter block. The front
matter is the provenance that citations render from, so it is validated hard:
a document with a missing or unknown field fails to load rather than being
silently ingested with a blank citation.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)

REQUIRED = {"doc_id", "title", "source", "attribution", "topic", "locator"}
KNOWN = REQUIRED | {
    "subtopic",
    "syllabus_section",
    "exam_board",
    "subject",
    "level",
    "year",
    "paper",
    "question_no",
}
VALID_ATTRIBUTION = {"syllabus", "worked_example", "past_question"}


class CorpusError(ValueError):
    pass


@dataclass
class SourceDocument:
    doc_id: str
    title: str
    source: str
    attribution: str
    topic: str
    locator: str
    body: str
    path: Path
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        payload = f"{self.doc_id}\n{self.title}\n{self.locator}\n{self.body}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def subtopic(self) -> str | None:
        return self.meta.get("subtopic")

    @property
    def syllabus_section(self) -> str | None:
        return self.meta.get("syllabus_section")

    def provenance(self) -> dict[str, Any]:
        """Exactly what the citation panel renders from."""
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "source": self.source,
            "attribution": self.attribution,
            "locator": self.locator,
            "topic": self.topic,
            "subtopic": self.subtopic,
            "syllabus_section": self.syllabus_section,
            "exam_board": self.meta.get("exam_board", "WAEC"),
            "subject": self.meta.get("subject", "Mathematics"),
            "level": self.meta.get("level", "SS3"),
            "year": self.meta.get("year"),
            "paper": self.meta.get("paper"),
            "question_no": self.meta.get("question_no"),
        }


def parse_document(text: str, path: Path) -> SourceDocument:
    m = FRONT_MATTER.match(text.replace("\r\n", "\n"))
    if not m:
        raise CorpusError(f"{path}: no YAML front matter found")

    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:  # pragma: no cover - defensive
        raise CorpusError(f"{path}: front matter is not valid YAML: {e}") from e

    if not isinstance(meta, dict):
        raise CorpusError(f"{path}: front matter must be a mapping")

    missing = REQUIRED - meta.keys()
    if missing:
        raise CorpusError(f"{path}: missing required front-matter keys: {sorted(missing)}")

    unknown = meta.keys() - KNOWN
    if unknown:
        raise CorpusError(f"{path}: unknown front-matter keys: {sorted(unknown)}")

    if meta["attribution"] not in VALID_ATTRIBUTION:
        raise CorpusError(
            f"{path}: attribution must be one of {sorted(VALID_ATTRIBUTION)}, "
            f"got {meta['attribution']!r}"
        )

    body = m.group(2).strip()
    if not body:
        raise CorpusError(f"{path}: document body is empty")

    return SourceDocument(
        doc_id=str(meta["doc_id"]),
        title=str(meta["title"]),
        source=str(meta["source"]),
        attribution=str(meta["attribution"]),
        topic=str(meta["topic"]),
        locator=str(meta["locator"]),
        body=body,
        path=path,
        meta={k: v for k, v in meta.items()},
    )


def load_file(path: Path) -> SourceDocument:
    return parse_document(path.read_text(encoding="utf-8"), path)


def load_dir(root: Path) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    seen: dict[str, Path] = {}
    for p in sorted(root.rglob("*.md")):
        d = load_file(p)
        if d.doc_id in seen:
            raise CorpusError(
                f"duplicate doc_id {d.doc_id!r} in {p} and {seen[d.doc_id]}"
            )
        seen[d.doc_id] = p
        docs.append(d)
    return docs
