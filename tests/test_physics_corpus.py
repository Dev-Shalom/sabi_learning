"""The Physics corpus, checked by something that did not write it.

`tools/build_physics_examples.py` computes each answer rather than typing it,
which removes one class of mistake. It does not remove the other: a formula
applied wrongly produces a confidently wrong answer that is arithmetically
consistent with itself.

So this file states the physics again, from scratch, and recomputes every
quantity from the givens parsed out of the markdown. It shares no code with
the generator. If the two ever disagree, one of them is wrong and the build
stops until somebody says which.

Modelled on `test_worked_example_arithmetic` in tests/test_corpus.py, which
does the same job for Mathematics.

WAEC convention: g = 10 m/s².
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from sabi.corpus.loader import load_dir

PHYSICS = Path(__file__).resolve().parent.parent / "corpus" / "physics"
G = 10.0

# Same shape a citation must take, from sabi/answer/generator.py. A locator
# that does not match is stripped from an answer, and if none survives the
# answer is discarded -- so a malformed one here is a silent failure later.
CITATION = re.compile(r"^[A-Z]{2,3}\s?[A-Z]?\d{1,3}(?:\.\d+)?$")

MIN_EXCLUSION_SECTIONS = 12


@pytest.fixture(scope="module")
def docs():
    loaded = load_dir(PHYSICS)
    assert loaded, "no Physics documents found"
    return loaded


@pytest.fixture(scope="module")
def by_id(docs):
    return {d.doc_id: d for d in docs}


# ------------------------------------------------------------------ shape


def test_every_document_declares_its_syllabus(docs):
    """Explicit, not defaulted.

    The Mathematics corpus relies on the subject default, which is how a
    part-written Physics corpus was able to be ingested as though it were
    Mathematics. These say what they are.
    """
    for d in docs:
        assert d.meta.get("subject") == "Physics", f"{d.doc_id} does not say Physics"
        assert d.meta.get("exam_board") == "WAEC", f"{d.doc_id} does not say WAEC"


def test_locators_are_unique_and_citable(docs):
    seen: dict[str, str] = {}
    for d in docs:
        assert CITATION.match(d.locator), (
            f"{d.doc_id} has locator {d.locator!r}, which the citation regex "
            "would not match -- it would be stripped from any answer"
        )
        assert d.locator not in seen, (
            f"{d.locator} used by both {d.doc_id} and {seen[d.locator]}"
        )
        seen[d.locator] = d.doc_id


def test_no_document_claims_a_real_past_paper(docs):
    """Sabi holds no licensed papers, so it must never imply otherwise."""
    for d in docs:
        for key in ("year", "paper", "question_no"):
            assert key not in d.meta, f"{d.doc_id} claims {key}"
        assert not re.search(r"\b(19|20)\d{2}\s+(WAEC|NECO)\b", d.body), (
            f"{d.doc_id} appears to cite a specific year's paper"
        )


def test_enough_documents_say_what_is_not_on_the_syllabus(docs):
    """Without these, Physics has no grounded refusals at all.

    A refusal that can cite the line saying a topic belongs to another course
    is a different thing from one that fires because a score fell below a
    number. The section heading is kept atomic by the chunker for this reason.
    """
    kept = [d for d in docs if "not on this syllabus" in d.body.lower()]
    assert len(kept) >= MIN_EXCLUSION_SECTIONS, (
        f"only {len(kept)} documents say what they exclude"
    )


def test_worked_examples_state_an_answer(docs):
    examples = [d for d in docs if d.attribution == "worked_example"]
    assert len(examples) >= 20
    for d in examples:
        assert "## Question" in d.body, f"{d.doc_id} has no question"
        assert "## Solution" in d.body, f"{d.doc_id} has no solution"
        assert re.search(r"\*\*Answer:.+\*\*", d.body), (
            f"{d.doc_id} does not end in a bold answer"
        )


# ------------------------------------------------------------- the physics
#
# Each entry recomputes the quantity from first principles and names the
# substring the document must contain. Nothing here reads the generator.

def _answer(doc) -> str:
    m = re.search(r"\*\*Answer:(.+?)\*\*", doc.body, re.S)
    assert m, f"{doc.doc_id} has no answer line"
    return m.group(1).strip()


def _near(value: float, dp: int = 2) -> str:
    r = round(value, dp)
    return str(int(r)) if r == int(r) else f"{r:.{dp}f}".rstrip("0").rstrip(".")


CHECKS = [
    # (doc_id, description, list of (computed value, decimal places))
    ("phy-ex-01-uniform-acceleration", "a=(v-u)/t and s=ut+at^2/2",
     [(20 / 8, 2), (0.5 * (20 / 8) * 64, 2)]),
    ("phy-ex-02-free-fall", "t=sqrt(2h/g), v=gt",
     [(math.sqrt(2 * 45 / G), 2), (G * math.sqrt(2 * 45 / G), 2)]),
    ("phy-ex-03-velocity-time-graph", "area under a v-t graph",
     [(0.5 * 15 * 4 + 15 * 6 + 0.5 * 15 * 5, 2)]),
    ("phy-ex-04-projectile-range", "T=2u.sin/g, R=u.cos.T",
     [(2 * 40 * 0.5 / G, 2)]),
    ("phy-ex-05-newton-second-law", "F=ma", [(1200 * 2.5, 2)]),
    ("phy-ex-06-momentum-collision", "conservation of momentum",
     [((3 * 4 + 2 * 0) / (3 + 2), 2)]),
    ("phy-ex-07-work-and-power", "W=Fd, P=W/t",
     [(250 * 12, 2), (250 * 12 / 6, 2)]),
    ("phy-ex-08-energy-conversion", "PE=mgh, v=sqrt(2gh)",
     [(0.5 * G * 20, 2), (math.sqrt(2 * G * 20), 2)]),
    ("phy-ex-09-machine-efficiency", "MA=L/E, VR=de/dl, eff=MA/VR",
     [(600 / 200, 2), (4 / 1, 2), (600 / 200 / (4 / 1) * 100, 2)]),
    ("phy-ex-10-pressure-in-a-liquid", "P=rho.g.h", [(1000 * G * 2.5, 2)]),
    ("phy-ex-11-upthrust", "upthrust = apparent loss in weight",
     [(5.0 - 3.2, 2)]),
    ("phy-ex-12-heat-capacity", "Q=mc.dtheta", [(2 * 4200 * 30, 2)]),
    ("phy-ex-13-latent-heat", "Q=mL", [(0.4 * 336000, 2)]),
    ("phy-ex-14-general-gas-law", "P1V1/T1 = P2V2/T2",
     [((100000 * 0.02 / 300) * (360 / 150000), 4)]),
    ("phy-ex-15-wave-equation", "v=f.lambda, T=1/f",
     [(50 * 6, 2), (1 / 50, 3)]),
    ("phy-ex-16-critical-angle", "sin C = 1/n", [(1 / 1.5, 4)]),
    ("phy-ex-17-lens-formula", "1/f=1/u+1/v, m=v/u",
     [(1 / (1 / 10 - 1 / 30), 2), ((1 / (1 / 10 - 1 / 30)) / 30, 3)]),
    ("phy-ex-18-resistors-combined", "parallel then series",
     [(1 / (1 / 6 + 1 / 3) + 4, 2)]),
    ("phy-ex-19-ohms-law-power", "I=V/R, P=VI",
     [(12 / 8, 2), (12 * (12 / 8), 2)]),
    ("phy-ex-20-transformer", "Vs = Vp.Ns/Np", [(240 * 250 / 1000, 2)]),
    ("phy-ex-21-half-life", "halve once per half-life",
     [(800 / 2 ** (20 / 5), 2)]),
]


@pytest.mark.parametrize("doc_id,what,values", CHECKS, ids=[c[0] for c in CHECKS])
def test_the_stated_answer_is_the_right_one(by_id, doc_id, what, values):
    """Recompute the physics and check the document agrees.

    The check is on the answer line specifically, not anywhere in the body:
    a number that appears only in the working is not what a student takes
    away.
    """
    doc = by_id.get(doc_id)
    assert doc is not None, f"{doc_id} is missing from the corpus"
    answer = _answer(doc)

    for value, dp in values:
        expected = _near(value, dp)
        assert expected in answer, (
            f"{doc_id} ({what}): recomputing gives {expected}, "
            f"which does not appear in the stated answer {answer!r}"
        )


def test_every_worked_example_is_checked(docs):
    """A new example must come with a check, or this test fails.

    Otherwise the suite quietly stops covering the corpus as it grows, which
    is the failure mode that makes a test suite look healthier than it is.
    """
    examples = {d.doc_id for d in docs if d.attribution == "worked_example"}
    checked = {c[0] for c in CHECKS}
    missing = examples - checked
    assert not missing, f"worked examples with no arithmetic check: {sorted(missing)}"


def test_gravity_is_stated_where_it_is_used(docs):
    """If a question depends on g, it must say which g."""
    for d in docs:
        if d.attribution != "worked_example":
            continue
        body = d.body.lower()
        uses_g = any(w in body for w in ("g = 10", "gravity", "falling", "weight"))
        if uses_g and "g = 10" in body:
            assert "10 m/s" in body, f"{d.doc_id} uses g without naming its units"
