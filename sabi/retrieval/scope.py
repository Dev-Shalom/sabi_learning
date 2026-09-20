"""Which syllabus a question is being asked against.

One question belongs to exactly one (exam board, subject) pair, and retrieval
only ever looks inside it. That is not a filter bolted onto search -- it is what
makes a citation mean anything once there is more than one syllabus in the
table, because "not on this syllabus" has to mean *which* syllabus.

## Why the predicate is a literal and not a bound parameter

`chunks.embedding` is searched through an HNSW index with `ORDER BY ... LIMIT n`.
Adding a bound `WHERE subject = $1` to that leaves Postgres post-filtering the
index walk, and the walk is bounded by `ef_search` -- so it runs out of
candidates and **returns fewer than `n` rows, or none, with no error at all**.
Fewer candidates means a shorter fused list, which means lower confidence, which
means the refusal threshold starts firing on answerable questions. Adding
Physics would look like a Mathematics bug.

The fix is a partial index per scope (see `sabi/schema.py`), and a partial index
is only matched when its predicate is provable at plan time -- which a bound
parameter in a generic plan is not. So the scope is interpolated as a literal.

Every value is therefore checked twice before it reaches SQL: against a
character whitelist, and against the set of scopes the configuration declares.
A value that fails either one raises rather than being escaped, because there is
no legitimate caller who needs a subject containing a quote.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from sabi.config import runtime

# Letters, digits, spaces and a hyphen. No quotes, no backslash, no semicolon.
SAFE = re.compile(r"^[A-Za-z][A-Za-z0-9 \-]{0,62}$")

DEFAULT_SUBJECT = "Mathematics"
DEFAULT_BOARD = "WAEC"


class ScopeError(ValueError):
    """A scope that is not configured, or not spellable in SQL."""


@lru_cache(maxsize=1)
def _declared() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The subjects and boards the configuration allows, from limits.yaml."""
    cfg = runtime()
    subjects = cfg.get("syllabus.subjects", [DEFAULT_SUBJECT])
    boards = cfg.get("syllabus.exam_boards", [DEFAULT_BOARD])
    return tuple(subjects), tuple(boards)


def declared_subjects() -> tuple[str, ...]:
    return _declared()[0]


def declared_boards() -> tuple[str, ...]:
    return _declared()[1]


def reset_cache() -> None:
    """limits.yaml is hot-reloaded, so the derived allow-list is too."""
    _declared.cache_clear()


@dataclass(frozen=True)
class RetrievalScope:
    """One syllabus. Frozen, so it cannot be mutated mid-request."""

    subject: str = DEFAULT_SUBJECT
    exam_board: str = DEFAULT_BOARD

    def __post_init__(self) -> None:
        for name, value in (("subject", self.subject), ("exam_board", self.exam_board)):
            if not SAFE.match(value or ""):
                raise ScopeError(f"{name} is not a usable value: {value!r}")
        # Checked against configuration as well as against the character set,
        # so an unconfigured subject cannot silently retrieve nothing.
        if self.subject not in declared_subjects():
            raise ScopeError(
                f"subject {self.subject!r} is not configured; "
                f"known: {', '.join(declared_subjects())}"
            )
        if self.exam_board not in declared_boards():
            raise ScopeError(
                f"exam_board {self.exam_board!r} is not configured; "
                f"known: {', '.join(declared_boards())}"
            )

    @property
    def key(self) -> str:
        """`WAEC:Mathematics`. Used for cache scoping and per-scope versions."""
        return f"{self.exam_board}:{self.subject}"

    @property
    def label(self) -> str:
        return f"{self.exam_board} {self.subject}"

    def predicate(self, alias: str = "c") -> str:
        """The SQL predicate, with literals so a partial index can match it.

        Safe because both values have already passed `SAFE` and the configured
        allow-list; this is not a general-purpose escaper and must not be used
        with anything that has not been through `RetrievalScope`.
        """
        return (
            f"{alias}.subject = '{self.subject}' "
            f"AND {alias}.exam_board = '{self.exam_board}'"
        )

    @classmethod
    def parse(
        cls, subject: str | None = None, exam_board: str | None = None
    ) -> RetrievalScope:
        """Build a scope from untrusted input, falling back to the defaults."""
        return cls(
            subject=(subject or DEFAULT_SUBJECT).strip() or DEFAULT_SUBJECT,
            exam_board=(exam_board or DEFAULT_BOARD).strip() or DEFAULT_BOARD,
        )

    @classmethod
    def safe_parse(
        cls, subject: str | None = None, exam_board: str | None = None
    ) -> RetrievalScope:
        """Like `parse`, but an unusable value falls back rather than raising.

        For request handling: a student who has bookmarked a URL with a subject
        that has since been retired should get the default, not a 500.
        """
        try:
            return cls.parse(subject, exam_board)
        except ScopeError:
            return cls()


DEFAULT_SCOPE = RetrievalScope()


def live_scopes() -> list[RetrievalScope]:
    """Every configured (board, subject) pair.

    Drives the picker, the per-scope index list, and the cross-subject redirect
    that recovers from a question asked under the wrong subject.
    """
    out: list[RetrievalScope] = []
    for board in declared_boards():
        for subject in declared_subjects():
            try:
                out.append(RetrievalScope(subject=subject, exam_board=board))
            except ScopeError:
                continue
    return out
