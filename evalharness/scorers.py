"""Deterministic scorers.

Everything here is code, not judgement. These run on every item, cost nothing,
and never disagree with themselves between runs. The LLM judge in `judge.py`
covers what cannot be checked this way.

Four families:

* **Retrieval** -- was the right source found at all? Scored at document level
  rather than chunk level, because chunk indices move when a document is edited
  and an eval set that breaks on a typo fix is an eval set nobody runs.
* **Citation integrity** -- is every citation shown to a student real? This is
  the product's central claim, so it is checked deterministically and a single
  violation is treated as a failure rather than a score.
* **Groundedness** -- can each substantive sentence be traced to cited text?
* **Refusal** -- did it refuse when it should have, and stay quiet when it
  should not have?
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sabi.retrieval.embeddings import tokenize
from sabi.textutil import logical_lines
from sabi.valuematch import contains_value, normalise_value  # noqa: F401

NUMERAL = re.compile(r"\d+(?:[.,]\d+)?")
SENTENCE = re.compile(r"(?<=[.;:])\s+(?=[A-Z(])")

# A sentence needs this many content terms before groundedness is scored on it.
# "Part (a)" and "So x = 2." carry no traceable claim of their own.
MIN_TERMS_FOR_GROUNDING = 5
SUPPORTED_AT = 0.8


# `normalise_value` and `contains_value` are imported from `sabi.valuematch`
# above rather than defined here. Practice marking needs the same judgement
# about whether two answers are the same number, and two implementations of
# that would drift -- one of them deciding 1/2 and 0.5 are the same answer
# and the other not. The harness's own question is narrower than practice's,
# so it uses `contains_value`: a paragraph of working legitimately contains
# more than the value, and a precision rule would reject it for that.


# ---------------------------------------------------------------- retrieval


@dataclass
class RetrievalScore:
    hit_at_1: bool
    hit_at_k: bool
    reciprocal_rank: float
    retrieved_docs: list[str]
    expected_docs: list[str]


def score_retrieval(expected_docs: list[str], retrieved_refs: list[str]) -> RetrievalScore:
    # A ref is "<doc_id>#<chunk_index>"; compare at document level.
    docs: list[str] = []
    for ref in retrieved_refs:
        doc = ref.split("#", 1)[0]
        if doc not in docs:
            docs.append(doc)

    wanted = set(expected_docs)
    rr = 0.0
    for i, doc in enumerate(docs, start=1):
        if doc in wanted:
            rr = 1.0 / i
            break

    return RetrievalScore(
        hit_at_1=bool(docs) and docs[0] in wanted,
        hit_at_k=bool(wanted & set(docs)),
        reciprocal_rank=rr,
        retrieved_docs=docs,
        expected_docs=sorted(wanted),
    )


# --------------------------------------------------------- citation integrity


@dataclass
class CitationScore:
    citations_shown: list[str]
    invalid: list[str]
    has_citation: bool

    @property
    def all_valid(self) -> bool:
        return not self.invalid


# Citation-shaped only. The first version of this matched any `[...]`, which
# reported five false failures on the first run: a worked solution legitimately
# contains `S(n) = (n/2) times [2a + (n - 1)d]` and `x = [7 plus or minus 5]`.
# Maths notation is not a citation. The pattern below is the same one the
# generator validates against and the same one the UI renders as a marker, so
# all three agree on what a citation looks like.
CITATION_IN_TEXT = re.compile(r"\[([A-Z]{2,3}\s?[A-Z]?\d{1,3}(?:\.\d+)?)\]")


def score_citations(answer_text: str, citation_locators: list[str]) -> CitationScore:
    """Every citation-shaped marker in the answer must be one the UI can render.

    The UI renders a panel per entry in `citations`. A locator in the prose with
    no matching panel is a citation a student cannot check -- which is the exact
    failure this product exists to prevent -- so it counts as invalid even
    though the text may be perfectly true.
    """
    in_text = [c.strip() for c in CITATION_IN_TEXT.findall(answer_text)]
    shown = set(citation_locators)
    invalid = sorted({c for c in in_text if c not in shown})
    return CitationScore(sorted(set(in_text)), invalid, bool(in_text))


# --------------------------------------------------------------- groundedness


@dataclass
class GroundednessScore:
    scored_sentences: int
    supported_sentences: int
    unsupported: list[str] = field(default_factory=list)
    unsourced_numerals: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        if not self.scored_sentences:
            return 1.0
        return self.supported_sentences / self.scored_sentences


def score_groundedness(answer_text: str, source_texts: list[str]) -> GroundednessScore:
    """Fraction of substantive sentences whose terms appear in the cited text.

    This is a traceability check, not a truth check: it asks whether a claim
    *came from* the sources, which is what "grounded" means here. Whether the
    claim is correct is the correctness metric's job.

    Known limitation, stated rather than hidden: a model that computes
    (12 - 2) x 180 = 1800 produces the numeral 1800, which may appear nowhere in
    the sources even though the step is sound. Unsourced numerals are therefore
    reported as a diagnostic, never as a failure.
    """
    source_terms: set[str] = set()
    source_numerals: set[str] = set()
    for t in source_texts:
        source_terms |= set(tokenize(t))
        source_numerals |= set(NUMERAL.findall(t))

    # Strip citation markers before scoring. A citation is not a claim, and its
    # tokens ("ex", "31") appear nowhere in the source text it points at -- so
    # counting them drags the coverage of every cited sentence down. Moving the
    # marker from its own line to the end of the sentence it supports dropped
    # the fully-grounded rate from 0.82 to 0.56 without changing a single
    # answer, which is how this was noticed.
    scored_text = CITATION_IN_TEXT.sub("", answer_text)

    units: list[str] = []
    for line in logical_lines(scored_text):
        units.extend(x.strip() for x in SENTENCE.split(line) if x.strip())

    scored = 0
    supported = 0
    unsupported: list[str] = []

    for sentence in units:
        terms = set(tokenize(sentence))
        if len(terms) < MIN_TERMS_FOR_GROUNDING:
            continue
        scored += 1
        coverage = len(terms & source_terms) / len(terms)
        if coverage >= SUPPORTED_AT:
            supported += 1
        else:
            unsupported.append(sentence)

    answer_numerals = set(NUMERAL.findall(answer_text))
    unsourced = sorted(answer_numerals - source_numerals)

    return GroundednessScore(scored, supported, unsupported, unsourced)


# -------------------------------------------------------------- correctness


@dataclass
class ValueScore:
    checked: bool
    passed: bool
    expected: str | None


def score_value(expected_value: str | None, answer_text: str) -> ValueScore:
    if not expected_value:
        return ValueScore(False, False, None)
    return ValueScore(True, contains_value(expected_value, answer_text), expected_value)


# ------------------------------------------------------------------ refusal


@dataclass
class RefusalScore:
    should_refuse: bool
    did_refuse: bool
    kind: str | None
    correct: bool
    failure_mode: str | None


def score_refusal(
    answerable: bool, unanswerable_kind: str | None, refused: bool, refusal_kind: str | None
) -> RefusalScore:
    should = not answerable
    correct = should == refused
    failure = None

    if should and not refused:
        # The dangerous direction: an out-of-syllabus question answered anyway.
        failure = "answered_unanswerable"
    elif not should and refused:
        failure = "over_refused"
    elif should and refused and unanswerable_kind == "welfare" and refusal_kind != "welfare":
        # Refusing for the wrong reason: the student gets a maths refusal when
        # they needed to be pointed at a person.
        correct = False
        failure = "welfare_missed"

    return RefusalScore(should, refused, refusal_kind, correct, failure)


# ------------------------------------------------------------------ latency


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def aggregate(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "mean": round(sum(values) / len(values), 4) if values else 0.0,
        "p50": round(percentile(values, 0.5), 4),
        "p95": round(percentile(values, 0.95), 4),
        "max": round(max(values), 4) if values else 0.0,
    }
