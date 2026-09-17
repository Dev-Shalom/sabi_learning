"""Corpus integrity: front matter, chunking rules, and the arithmetic itself."""

from __future__ import annotations

import math
from fractions import Fraction as F
from pathlib import Path

import pytest

from sabi.corpus.chunker import MAX_WORDS, chunk_document
from sabi.corpus.loader import CorpusError, load_dir, parse_document

CORPUS = Path(__file__).resolve().parent.parent / "corpus"


def test_every_document_loads():
    docs = load_dir(CORPUS)
    assert len(docs) >= 80
    assert {d.attribution for d in docs} <= {"syllabus", "worked_example", "past_question"}


def test_no_fabricated_exam_citations():
    """The product's claim is honest citation, so this is enforced, not trusted.

    No corpus document may claim a year or a question number unless it is
    genuinely attributed to a past paper. Authored practice items must not
    acquire exam metadata by a careless copy-paste of front matter.
    """
    for doc in load_dir(CORPUS):
        if doc.attribution != "past_question":
            assert doc.meta.get("year") is None, f"{doc.doc_id} claims a year"
            assert doc.meta.get("question_no") is None, f"{doc.doc_id} claims a question number"


def test_locators_are_unique_per_document():
    locators = [d.locator for d in load_dir(CORPUS)]
    assert len(set(locators)) == len(locators)


def test_worked_solution_is_never_split():
    for doc in load_dir(CORPUS):
        for chunk in chunk_document(doc):
            if (chunk.heading or "").lower().startswith("solution"):
                assert chunk.atomic, f"{doc.doc_id} chunk {chunk.index} is a split solution"


def test_exclusion_sections_survive_chunking():
    """Grounded refusals depend on these keeping their own heading."""
    kept = 0
    for doc in load_dir(CORPUS):
        if "## Not on this syllabus" not in doc.body:
            continue
        headings = [(c.heading or "").lower() for c in chunk_document(doc)]
        assert "not on this syllabus" in headings, f"{doc.doc_id} lost its exclusion section"
        kept += 1
    assert kept >= 10


def test_non_atomic_chunks_respect_the_size_ceiling():
    for doc in load_dir(CORPUS):
        for chunk in chunk_document(doc):
            if not chunk.atomic:
                assert chunk.word_count <= MAX_WORDS, f"{doc.doc_id}#{chunk.index}"


def test_front_matter_is_validated():
    with pytest.raises(CorpusError):
        parse_document("no front matter here", Path("x.md"))
    with pytest.raises(CorpusError):
        parse_document(
            "---\ndoc_id: x\ntitle: t\n---\nbody", Path("x.md")
        )  # missing required keys
    with pytest.raises(CorpusError):
        parse_document(
            "---\ndoc_id: x\ntitle: t\nsource: s\nattribution: invented\n"
            "topic: t\nlocator: L1\n---\nbody",
            Path("x.md"),
        )


# --------------------------------------------------------------------------
# The worked examples state numeric answers. If one of them is wrong, students
# get taught the wrong thing and the golden set bakes it in. Every value is
# recomputed here independently of the text that claims it.

ARITHMETIC = {
    "EX 01 base five to ten": (3 * 125 + 4 * 25 + 1 * 5 + 2, 482),
    "EX 02 unknown base": (5**2 + 3 * 5 + 2, 42),
    "EX 03 binary sum": (0b1011 + 0b1101, 0b11000),
    "EX 05 percentage error": (0.1 / 2.5 * 100, 4.0),
    "EX 07 fractional indices": (27 ** (2 / 3) * 16**-0.5, 2.25),
    "EX 08 log 12": (2 * 0.3010 + 0.4771, 1.0791),
    "EX 09 log equation root": (5 * (5 - 3), 10),
    "EX 10 two-set venn": (25 + 20 - (40 - 8), 13),
    "EX 11 three-set venn": (100 - (60 + 50 + 40 - 30 - 25 - 20 + 10), 15),
    "EX 14 AP sum": ((20 / 2) * (2 * -1 + 19 * 3), 550),
    "EX 15 GP sum": (3 * (2**8 - 1) / (2 - 1), 765),
    "EX 16 sum to infinity": (18 / (1 - 1 / 3), 27),
    "EX 17 determinant": (2 * 4 - 3 * 1, 5),
    "EX 18 simultaneous x": ((4 * 13 - 3 * 14) / 5, 2),
    "EX 18 simultaneous y": ((-1 * 13 + 2 * 14) / 5, 3),
    "EX 19 principal": (100 * 4500 / (6 * 3), 25000),
    "EX 20 compound amount": (50000 * 1.1**3, 66550),
    "EX 21 hire purchase": (30000 + 12 * 9000, 138000),
    "EX 21 extra percent": ((138000 - 120000) / 120000 * 100, 15),
    "EX 22 joint variation": (36 / 3, 12),
    "EX 23 partial variation": (3 + 2 * 10, 23),
    "EX 28 quadratic roots": ((7 + 5) / 6, 2),
    "EX 29 completed square": ((3 - 3) ** 2 - 4, 3**2 - 6 * 3 + 5),
    "EX 31 polygon sum": ((12 - 2) * 180, 1800),
    "EX 31 each interior": (1800 / 12, 150),
    "EX 32 sides": (360 / 24, 15),
    "EX 32 interior sum": ((15 - 2) * 180, 2340),
    "EX 33 angle at circumference": (130 / 2, 65),
    "EX 34 cyclic opposite": (180 - 78, 102),
    "EX 36 slant height": (math.hypot(7, 24), 25),
    "EX 36 cone total surface": (float(F(22, 7) * 7 * 25 + F(22, 7) * 49), 704),
    "EX 38 latitude distance": (
        30 / 360 * 2 * (22 / 7) * 6400 * math.cos(math.radians(60)),
        1676.19,
    ),
    "EX 39 sine rule": (
        10 * math.sin(math.radians(60)) / math.sin(math.radians(45)), 12.247
    ),
    "EX 40 cosine rule": (math.sqrt(49 + 81 - 2 * 7 * 9 * 0.5), 8.185),
    "EX 41 bearing distance": (math.hypot(60, 80), 100),
    "EX 42 elevation height": (50 * math.tan(math.radians(32)), 31.245),
    "EX 43 minimum y": (3**3 - 3 * 3**2 - 9 * 3 + 5, -22),
    "EX 43 maximum y": ((-1) ** 3 - 3 * (-1) ** 2 - 9 * (-1) + 5, 10),
    "EX 44 definite integral": ((27 - 18 + 15) - (1 - 2 + 5), 20),
    "EX 46 grouped mean": ((4 * 3 + 8 * 8 + 12 * 13 + 10 * 18 + 6 * 23) / 40, 13.75),
    "EX 47 standard deviation": (math.sqrt(40 / 5), 2.828),
    "EX 49 vector magnitude": (math.hypot(5, -12), 13),
}

EXACT = {
    "EX 35 arc length": (F(90, 360) * 2 * F(22, 7) * 14, F(22)),
    "EX 35 sector area": (F(90, 360) * F(22, 7) * 196, F(154)),
    "EX 36 cone volume": (F(1, 3) * F(22, 7) * 49 * 24, F(1232)),
    "EX 37 sphere volume": (F(4, 3) * F(22, 7) * F(21, 2) ** 3, F(4851)),
    "EX 37 sphere surface": (4 * F(22, 7) * F(21, 2) ** 2, F(1386)),
    "EX 45 area under curve": (
        (4 * 2 - F(8, 3)) - (4 * -2 + F(8, 3)), F(32, 3)
    ),
    "EX 48 probability both red": (F(5, 10) * F(4, 9), F(2, 9)),
}


@pytest.mark.parametrize("label", sorted(ARITHMETIC))
def test_worked_example_arithmetic(label):
    computed, claimed = ARITHMETIC[label]
    assert computed == pytest.approx(claimed, rel=1e-3), label


@pytest.mark.parametrize("label", sorted(EXACT))
def test_worked_example_exact_fractions(label):
    computed, claimed = EXACT[label]
    assert computed == claimed, label
