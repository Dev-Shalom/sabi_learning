"""The golden set knows which syllabus each item is asked under.

Until now every item was implicitly WAEC Mathematics, which is fine while there
is one subject and silently wrong on the day there are two: a global recall
number cannot show one subject regressing while the other improves.
"""

from __future__ import annotations

import json

from evalharness.dataset import SEED_PATH, _from_dict, load_seed, summarise
from evalharness.runner import ItemResult, aggregate


def _item(**overrides) -> ItemResult:
    base = dict(
        slug="g-000", question="q", slice="answerable", topic="Surds",
        subject="Mathematics", exam_board="WAEC", answerable=True, refused=False,
        refusal_kind=None, answer="a [EX 1]", model=None, confidence=0.9,
        latency_ms=10, cost_usd=0.0, cost_is_estimated=True,
        retrieval={"hit_at_k": True, "hit_at_1": True, "reciprocal_rank": 1.0},
        citations={"invalid": [], "has_citation": True},
        grounding={"ratio": 1.0, "unsourced_numerals": []},
        value={"checked": False, "passed": False},
        refusal={"correct": True},
        verdict={"correctness": 2, "groundedness": 2},
        failures=[],
    )
    return ItemResult(**(base | overrides))


def test_every_seed_item_names_its_syllabus():
    items = load_seed()
    assert len(items) == 100
    assert {(i.exam_board, i.subject) for i in items} == {("WAEC", "Mathematics")}
    assert all(i.scope_name == "WAEC:Mathematics" for i in items)


def test_the_seed_file_carries_the_columns_rather_than_relying_on_the_default():
    """The file is the record. A default that is never written is not a tag."""
    rows = [
        json.loads(line)
        for line in SEED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all(r["subject"] == "Mathematics" for r in rows)
    assert all(r["exam_board"] == "WAEC" for r in rows)


def test_an_item_written_before_the_columns_existed_still_loads():
    item = _from_dict(
        {
            "slug": "g-legacy",
            "question": "Simplify 3 root 2 plus 5 root 2",
            "answerable": True,
            "expected_docs": ["ex-12-simplify-surds"],
        }
    )
    assert item.subject == "Mathematics"
    assert item.exam_board == "WAEC"


def test_the_summary_counts_items_per_subject():
    assert summarise(load_seed())["subjects"] == {"Mathematics": 100}


def test_by_subject_has_the_same_shape_as_by_topic():
    metrics = aggregate(
        [
            _item(slug="g-001"),
            _item(slug="g-002", retrieval={"hit_at_k": False, "hit_at_1": False,
                                           "reciprocal_rank": 0.0},
                  failures=["retrieval_miss"]),
            _item(slug="p-001", subject="Physics", topic="Waves"),
        ]
    )
    assert set(metrics["by_subject"]) == {"Mathematics", "Physics"}
    assert set(metrics["by_subject"]["Mathematics"]) == set(
        metrics["by_topic"]["Surds"]
    )
    assert metrics["by_subject"]["Mathematics"] == {
        "n": 2, "retrieval_hits": 1, "failures": 1, "recall": 0.5,
    }
    assert metrics["by_subject"]["Physics"]["recall"] == 1.0
