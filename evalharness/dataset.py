"""Loading the golden dataset.

Two sources, one shape:

* `eval/golden/seed.jsonl` -- the hand-built seed set, in version control, so a
  clone of the repo can run the suite with no database.
* the `golden_items` table -- items promoted from real down-votes. This is how
  the set grows past its initial 100, and it is the reason the feedback schema
  was made compatible with this one: promoting an entry is a data move.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = REPO_ROOT / "eval" / "golden" / "seed.jsonl"

UNANSWERABLE_KINDS = {"out_of_syllabus", "out_of_subject", "not_in_corpus", "welfare"}


@dataclass
class GoldenItem:
    slug: str
    question: str
    answerable: bool
    expected_docs: list[str] = field(default_factory=list)
    expected_value: str | None = None
    expected_answer: str | None = None
    unanswerable_kind: str | None = None
    topic: str = ""
    difficulty: str = ""
    notes: str | None = None
    origin: str = "seed"

    @property
    def slice_name(self) -> str:
        return "answerable" if self.answerable else f"unanswerable:{self.unanswerable_kind}"


def _from_dict(d: dict[str, Any]) -> GoldenItem:
    item = GoldenItem(
        slug=d["slug"],
        question=d["question"],
        answerable=bool(d["answerable"]),
        expected_docs=list(d.get("expected_docs") or []),
        expected_value=d.get("expected_value"),
        expected_answer=d.get("expected_answer"),
        unanswerable_kind=d.get("unanswerable_kind"),
        topic=d.get("topic") or "",
        difficulty=d.get("difficulty") or "",
        notes=d.get("notes"),
        origin=d.get("origin") or "seed",
    )
    if not item.answerable and item.unanswerable_kind not in UNANSWERABLE_KINDS:
        raise ValueError(
            f"{item.slug}: unanswerable_kind must be one of {sorted(UNANSWERABLE_KINDS)}"
        )
    if item.answerable and not item.expected_docs:
        raise ValueError(f"{item.slug}: an answerable item needs expected_docs")
    return item


def load_seed(path: Path | None = None) -> list[GoldenItem]:
    p = path or SEED_PATH
    items = [_from_dict(json.loads(line)) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    slugs = [i.slug for i in items]
    dupes = {s for s in slugs if slugs.count(s) > 1}
    if dupes:
        raise ValueError(f"duplicate slugs in {p}: {sorted(dupes)}")
    return items


def load_promoted() -> list[GoldenItem]:
    """Items promoted from down-voted answers. Empty if the DB is unreachable."""
    try:
        from sqlalchemy import select

        from sabi.db import session_scope
        from sabi.models import GoldenItem as GoldenRow

        with session_scope() as s:
            rows = s.execute(select(GoldenRow).where(GoldenRow.active)).scalars().all()
            return [
                GoldenItem(
                    slug=r.slug,
                    question=r.question,
                    answerable=r.answerable,
                    expected_docs=list(r.expected_docs or []),
                    expected_value=r.expected_value,
                    expected_answer=r.expected_answer,
                    unanswerable_kind=r.unanswerable_kind,
                    topic=r.topic or "",
                    difficulty=r.difficulty or "",
                    notes=r.notes,
                    origin=r.origin,
                )
                for r in rows
            ]
    except Exception:
        return []


def load_all(include_promoted: bool = True) -> list[GoldenItem]:
    items = load_seed()
    if include_promoted:
        seen = {i.slug for i in items}
        items.extend(i for i in load_promoted() if i.slug not in seen)
    return items


def summarise(items: Iterable[GoldenItem]) -> dict[str, Any]:
    items = list(items)
    kinds: dict[str, int] = {}
    for i in items:
        if not i.answerable:
            kinds[i.unanswerable_kind or "?"] = kinds.get(i.unanswerable_kind or "?", 0) + 1
    return {
        "total": len(items),
        "answerable": sum(1 for i in items if i.answerable),
        "unanswerable": sum(1 for i in items if not i.answerable),
        "unanswerable_kinds": kinds,
        "with_value_check": sum(1 for i in items if i.expected_value),
        "promoted": sum(1 for i in items if i.origin == "feedback"),
    }
