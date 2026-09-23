"""Loading exam formats, and refusing the ones that cannot be trusted.

An exam format is data (`exam_formats/*.yaml`) validated against a frozen
contract (`contracts/exam_format.schema.json`). Exam mode reads the loaded
config and nothing else, so adding NECO or a university's Post-UTME is a file
rather than a branch in the simulator -- and each exam's conformance test can
be generated from its own config, which only means anything if the simulator
has no hard-coded knowledge to disagree with it.

Two rules are enforced here rather than left to reviewers:

* **No source, no load.** `source_url` and `verified_on` are required by the
  schema. Nigerian exam formats move between seasons -- WAEC's CBT transition
  moved twice while this was being specified -- so a config nobody can trace
  to an official page is a config nobody can re-check.
* **Dates are coerced before validation.** YAML parses a bare `2026-09-23`
  into a `datetime.date`, which is not a JSON string, so every config would
  otherwise fail validation on its own `verified_on` field. Found by
  validating rather than by assuming.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
FORMAT_DIR = ROOT / "exam_formats"
SCHEMA_PATH = ROOT / "contracts" / "exam_format.schema.json"

# How stale a format may be before it is worth re-checking. Not an expiry --
# the config still loads -- but `stale_formats()` reports it, and the answer
# to "is this still true?" should be looked at before each exam season.
STALE_AFTER_DAYS = 365


class FormatError(ValueError):
    """A format file that cannot be trusted. Carries what is wrong with it."""


@dataclass(frozen=True)
class ExamFormat:
    """One validated exam format."""

    key: str
    data: dict[str, Any]
    path: Path

    @property
    def exam_body(self) -> str:
        return self.data["exam_body"]

    @property
    def total_questions(self) -> int:
        return sum(s["question_count"] for s in self.data["sections"])

    @property
    def option_labels(self) -> list[str]:
        # Defaulted here rather than assumed at the call site: NECO objective
        # papers use five options, so a component that hard-codes four would
        # have a student practising against three distractors.
        return self.data.get("option_labels", ["A", "B", "C", "D"])

    @property
    def verified_on(self) -> _dt.date:
        return _dt.date.fromisoformat(self.data["verified_on"])

    @property
    def days_since_verified(self) -> int:
        return (_dt.date.today() - self.verified_on).days

    @property
    def is_stale(self) -> bool:
        return self.days_since_verified > STALE_AFTER_DAYS


def _jsonable(value: Any) -> Any:
    """Make a YAML document comparable to a JSON Schema.

    Only dates need this, and they need it badly: a bare `2026-09-23` in YAML
    is a `datetime.date`, and JSON Schema's `"type": "string"` rejects it.
    """
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    return value


@lru_cache(maxsize=1)
def _validator():
    from jsonschema import Draft202012Validator

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def load_file(path: Path) -> ExamFormat:
    """Load and validate one format file, or raise with what is wrong."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise FormatError(f"{path.name}: not valid YAML -- {e}") from e

    if not isinstance(raw, dict):
        raise FormatError(f"{path.name}: expected a mapping at the top level")

    data = _jsonable(raw)
    errors = sorted(_validator().iter_errors(data), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in errors[:5]
        )
        raise FormatError(f"{path.name}: {detail}")

    return ExamFormat(key=path.stem, data=data, path=path)


@lru_cache(maxsize=1)
def load_all() -> dict[str, ExamFormat]:
    """Every format in `exam_formats/`, keyed by filename stem.

    Cached: a format is configuration, read once per process. `load_all.cache_clear()`
    after editing one in a test.
    """
    if not FORMAT_DIR.exists():
        return {}
    out: dict[str, ExamFormat] = {}
    for path in sorted(FORMAT_DIR.glob("*.yaml")):
        out[path.stem] = load_file(path)
    return out


def get(key: str) -> ExamFormat:
    formats = load_all()
    if key not in formats:
        raise FormatError(
            f"no exam format named {key!r}; have {sorted(formats)}"
        )
    return formats[key]


def for_body(exam_body: str) -> list[ExamFormat]:
    return [f for f in load_all().values() if f.exam_body == exam_body]


def stale_formats() -> list[ExamFormat]:
    """Formats that should be re-checked against the exam body before a season."""
    return [f for f in load_all().values() if f.is_stale]
