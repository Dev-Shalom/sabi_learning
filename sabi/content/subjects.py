"""The subject catalog, seeded from the frozen contract.

`contracts/subject_codes.yaml` is the single registry of subject codes, so
that two subjects cannot collide on one -- a collision means two subjects
citing the same locator and a student following a citation into the wrong
syllabus.

This syncs that file into the `subjects` table, which is where `available`
lives. The two are not the same fact:

* the **contract** says a subject exists and owns a code;
* the **table** says whether a student may be offered it today.

A subject becomes available only when it has enough verified content, which is
a question about the bank, not about the registry. Showing a subject that
yields an empty practice set is worse than not showing it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sabi.models import Question, Subject

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY = ROOT / "contracts" / "subject_codes.yaml"

# How many verified questions a subject needs before it is offered. Set low
# enough to be reachable in the content pilot and high enough that a set of 10
# is never drawn from a pool of 12, which would show a student the same
# question twice in a week.
AVAILABILITY_THRESHOLD = 60


@dataclass(frozen=True)
class RegistryEntry:
    code: str
    name: str
    track: str
    wave: int
    verified: bool


def load_registry() -> list[RegistryEntry]:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    reserved = set(data.get("reserved", []))

    entries: list[RegistryEntry] = []
    seen: set[str] = set()
    for row in data["subjects"]:
        code = row["code"]
        if code in seen:
            raise ValueError(f"duplicate subject code in the registry: {code}")
        if code in reserved:
            raise ValueError(
                f"subject code {code} collides with a reserved locator prefix"
            )
        seen.add(code)
        entries.append(
            RegistryEntry(
                code=code,
                name=row["name"],
                track=row.get("track", "any"),
                wave=int(row.get("wave", 2)),
                verified=bool(row.get("verified", False)),
            )
        )
    return entries


def sync(s: Session) -> list[str]:
    """Push the registry into the table. Never sets `available`.

    `available` is derived from the bank by `refresh_availability`, so a sync
    cannot accidentally switch a subject on: the registry does not know how
    much verified content exists.
    """
    changed: list[str] = []
    for entry in load_registry():
        row = s.get(Subject, entry.code)
        fields = dict(
            name=entry.name,
            track=entry.track,
            wave=entry.wave,
            verified=entry.verified,
        )
        if row is None:
            s.add(Subject(code=entry.code, available=False, **fields))
            changed.append(f"added {entry.code} ({entry.name})")
        else:
            diff = [k for k, v in fields.items() if getattr(row, k) != v]
            if diff:
                for k, v in fields.items():
                    setattr(row, k, v)
                changed.append(f"updated {entry.code}: {', '.join(diff)}")
    return changed


def verified_counts(s: Session) -> dict[str, int]:
    """Servable questions per subject.

    The same predicate every student-facing read uses: verified, and not
    dev-only. Counting anything looser here would switch a subject on because
    of questions nobody may see.
    """
    rows = s.execute(
        select(Question.subject_code, func.count())
        .where(Question.status == "verified", Question.licence != "dev_only")
        .group_by(Question.subject_code)
    ).all()
    return {r[0]: int(r[1]) for r in rows}


def refresh_availability(s: Session, threshold: int = AVAILABILITY_THRESHOLD) -> list[str]:
    """Switch subjects on and off from what the bank actually holds."""
    counts = verified_counts(s)
    changed: list[str] = []
    for row in s.execute(select(Subject)).scalars():
        should = counts.get(row.code, 0) >= threshold
        if row.available != should:
            row.available = should
            changed.append(
                f"{row.code} {'available' if should else 'withdrawn'} "
                f"({counts.get(row.code, 0)} verified)"
            )
    return changed
