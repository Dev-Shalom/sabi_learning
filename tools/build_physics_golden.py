#!/usr/bin/env python
"""Generate the Physics slice of the golden set.

A subject with no golden items is a subject nobody is measuring, and this
project's whole claim is that its quality is measured rather than asserted.
So Physics does not get switched on until it has a slice of its own.

The answerable items are derived from the worked examples, so the expected
value in the golden set and the answer in the corpus cannot drift apart --
both come from the same computation in `build_physics_examples.py`, and
`tests/test_physics_corpus.py` independently checks that computation.

The unanswerable items are hand-written, because what a syllabus *excludes*
is a judgement rather than a calculation. Each one names the exclusion
section that should ground the refusal.

    python tools/build_physics_golden.py            # writes the slice
    python tools/build_physics_golden.py --merge    # folds it into seed.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "eval" / "golden" / "seed.jsonl"
SLICE = ROOT / "eval" / "golden" / "physics.jsonl"
EXAMPLES = ROOT / "corpus" / "physics" / "examples"

SUBJECT = "Physics"
BOARD = "WAEC"


def item(**kw) -> dict:
    """A golden item with the keys in the same order as the existing file."""
    base = {
        "slug": kw["slug"],
        "question": kw["question"],
        "answerable": kw.get("answerable", True),
        "expected_docs": kw.get("expected_docs", []),
        "expected_value": kw.get("expected_value"),
        "expected_answer": kw.get("expected_answer"),
        "topic": kw.get("topic", ""),
        "difficulty": kw.get("difficulty", "medium"),
        "notes": kw.get("notes"),
        "origin": "seed",
        "subject": SUBJECT,
        "exam_board": BOARD,
    }
    if not base["answerable"]:
        base["unanswerable_kind"] = kw["unanswerable_kind"]
    return base


# The question each worked example answers, phrased the way a student would
# type it rather than the way the corpus states it -- otherwise the retrieval
# test is a string match and proves nothing.
ASKED = {
    "phy-ex-01-uniform-acceleration": (
        "A car goes from rest to 20 m/s in 8 seconds, what is the acceleration",
        "2.5", "Motion", "easy"),
    "phy-ex-02-free-fall": (
        "How long does a stone take to fall 45 m from rest",
        "3", "Motion", "easy"),
    "phy-ex-03-velocity-time-graph": (
        "How do I find distance from the area under a velocity time graph",
        None, "Motion", "medium"),
    "phy-ex-04-projectile-range": (
        "Find the time of flight of a ball thrown at 40 m/s at 30 degrees",
        "4", "Projectiles", "medium"),
    "phy-ex-05-newton-second-law": (
        "What force accelerates a 1200 kg car at 2.5 m/s squared",
        "3000", "Newton's laws", "easy"),
    "phy-ex-06-momentum-collision": (
        "A 3 kg trolley at 4 m/s hits a stationary 2 kg trolley and they stick, "
        "find their speed",
        "2.4", "Momentum", "medium"),
    "phy-ex-07-work-and-power": (
        "Work done pushing a crate 12 m with a force of 250 N",
        "3000", "Work and energy", "easy"),
    "phy-ex-08-energy-conversion": (
        "A 0.5 kg ball falls from 20 m, what is its potential energy",
        "100", "Work and energy", "easy"),
    "phy-ex-09-machine-efficiency": (
        "How do I calculate the efficiency of a machine from MA and VR",
        None, "Machines", "medium"),
    "phy-ex-10-pressure-in-a-liquid": (
        "Pressure of water at a depth of 2.5 m",
        "25000", "Pressure", "easy"),
    "phy-ex-11-upthrust": (
        "A block weighs 5 N in air and 3.2 N in water, what is the upthrust",
        "1.8", "Pressure", "easy"),
    "phy-ex-12-heat-capacity": (
        "Heat needed to raise 2 kg of water by 30 degrees",
        "252000", "Heat", "medium"),
    "phy-ex-13-latent-heat": (
        "How much heat melts 0.4 kg of ice at zero degrees",
        "134400", "Heat", "medium"),
    "phy-ex-14-general-gas-law": (
        "How do I use the general gas law when pressure and temperature both "
        "change",
        None, "Gas laws", "hard"),
    "phy-ex-15-wave-equation": (
        "Speed of a wave with frequency 50 Hz and wavelength 6 m",
        "300", "Waves", "easy"),
    "phy-ex-16-critical-angle": (
        "What is the critical angle for glass of refractive index 1.5",
        None, "Refraction", "medium"),
    "phy-ex-17-lens-formula": (
        "Object 30 cm from a converging lens of focal length 10 cm, where is "
        "the image",
        "15", "Lenses", "medium"),
    "phy-ex-18-resistors-combined": (
        "6 ohm and 3 ohm in parallel then 4 ohm in series, total resistance",
        "6", "Current electricity", "medium"),
    "phy-ex-19-ohms-law-power": (
        "Current through an 8 ohm resistor on a 12 V battery",
        "1.5", "Current electricity", "easy"),
    "phy-ex-20-transformer": (
        "Transformer with 1000 primary turns and 250 secondary on 240 V, find "
        "the output",
        "60", "Induction", "medium"),
    "phy-ex-21-half-life": (
        "Count rate after 20 days if the half life is 5 days and it starts at 800",
        "50", "Radioactivity", "medium"),
}


# The syllabus document covering the same ground as each worked example.
#
# Both count as a hit, because `score_retrieval` treats `expected_docs` as
# "any of these". The two measurements are deliberately separate: recall asks
# whether relevant material was found at all, and the value check asks whether
# the answer is right. A conceptual question -- "how do I work out efficiency"
# -- is better served by the syllabus text than by one worked example of it,
# and scoring that as a miss would be measuring the wrong thing.
COVERS = {
    "phy-ex-01-uniform-acceleration": "phy-syl-a03-linear-motion",
    "phy-ex-02-free-fall": "phy-syl-a03-linear-motion",
    "phy-ex-03-velocity-time-graph": "phy-syl-a03-linear-motion",
    "phy-ex-04-projectile-range": "phy-syl-a04-projectiles",
    "phy-ex-05-newton-second-law": "phy-syl-a06-newton-momentum",
    "phy-ex-06-momentum-collision": "phy-syl-a06-newton-momentum",
    "phy-ex-07-work-and-power": "phy-syl-b01-work-energy-power",
    "phy-ex-08-energy-conversion": "phy-syl-b01-work-energy-power",
    "phy-ex-09-machine-efficiency": "phy-syl-b02-simple-machines",
    "phy-ex-10-pressure-in-a-liquid": "phy-syl-c01-pressure-fluids",
    "phy-ex-11-upthrust": "phy-syl-c01-pressure-fluids",
    "phy-ex-12-heat-capacity": "phy-syl-c03-heat-capacity-latent-heat",
    "phy-ex-13-latent-heat": "phy-syl-c03-heat-capacity-latent-heat",
    "phy-ex-14-general-gas-law": "phy-syl-c04-gas-laws",
    "phy-ex-15-wave-equation": "phy-syl-d01-waves-sound",
    "phy-ex-16-critical-angle": "phy-syl-d02-reflection-refraction",
    "phy-ex-17-lens-formula": "phy-syl-d03-lenses-optical-instruments",
    "phy-ex-18-resistors-combined": "phy-syl-e02-current-electricity",
    "phy-ex-19-ohms-law-power": "phy-syl-e02-current-electricity",
    "phy-ex-20-transformer": "phy-syl-e03-magnetism-induction",
    "phy-ex-21-half-life": "phy-syl-f02-atomic-nuclear",
}


def answerable_items() -> list[dict]:
    out: list[dict] = []
    for i, (doc_id, (question, value, topic, difficulty)) in enumerate(
        sorted(ASKED.items()), start=1
    ):
        path = EXAMPLES / f"{doc_id}.md"
        if not path.is_file():
            raise SystemExit(f"missing worked example: {path}")
        body = path.read_text(encoding="utf-8")
        m = re.search(r"\*\*Answer:(.+?)\*\*", body, re.S)
        if not m:
            raise SystemExit(f"{doc_id} has no answer line")
        out.append(item(
            slug=f"p-{i:03d}",
            question=question,
            expected_docs=[doc_id] + ([COVERS[doc_id]] if doc_id in COVERS else []),
            expected_value=value,
            expected_answer=m.group(1).strip(),
            topic=topic,
            difficulty=difficulty,
        ))
    return out


# Hand-written. Each names the exclusion section that should ground the
# refusal, so a failure says which document needs work rather than only that
# the confidence was low.
UNANSWERABLE = [
    ("Derive the equations of motion using calculus",
     "out_of_syllabus", "Motion",
     "Calculus derivations belong to Further Physics; PHY A3 excludes them."),
    ("Explain time dilation in special relativity",
     "out_of_syllabus", "Relativity",
     "Relativity is not on the Core Physics syllabus."),
    ("What does the Schrodinger equation say about an electron",
     "out_of_syllabus", "Quantum mechanics",
     "Quantum mechanics beyond the photoelectric equation is excluded."),
    ("State Maxwell's equations",
     "out_of_syllabus", "Electromagnetism",
     "Maxwell's equations are beyond the syllabus; PHY E3 excludes them."),
    ("Write a 500 word essay on the importance of physics in Nigeria",
     "out_of_subject", "Essay",
     "Not a physics calculation or a syllabus point; nothing to ground."),
    ("What was question 4 on the 2019 WAEC physics paper 2",
     "not_in_corpus", "Past papers",
     "Sabi holds no licensed past papers and must not invent one."),
]


def unanswerable_items() -> list[dict]:
    start = len(ASKED) + 1
    return [
        item(
            slug=f"p-{start + i:03d}",
            question=question,
            answerable=False,
            unanswerable_kind=kind,
            topic=topic,
            difficulty="n/a",
            notes=note,
        )
        for i, (question, kind, topic, note) in enumerate(UNANSWERABLE)
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge", action="store_true",
                    help="append the slice to eval/golden/seed.jsonl")
    args = ap.parse_args()

    items = answerable_items() + unanswerable_items()
    slugs = [i["slug"] for i in items]
    if len(set(slugs)) != len(slugs):
        raise SystemExit("duplicate slugs in the generated slice")

    SLICE.write_text(
        "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items),
        encoding="utf-8",
    )
    answerable = sum(1 for i in items if i["answerable"])
    print(f"wrote {len(items)} items to {SLICE.relative_to(ROOT)} "
          f"({answerable} answerable, {len(items) - answerable} unanswerable)")

    if not args.merge:
        print("not merged. Re-run with --merge to fold it into seed.jsonl")
        return 0

    existing = [
        json.loads(line)
        for line in SEED.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # Replace any earlier Physics slice rather than refusing. This file is
    # generated, so running it twice should converge on the same result --
    # and while the slice is being tuned it will be run many times.
    kept = [e for e in existing if not e["slug"].startswith("p-")]
    replaced = len(existing) - len(kept)

    clash = {e["slug"] for e in kept} & set(slugs)
    if clash:
        raise SystemExit(f"generated slugs clash with hand-written ones: {sorted(clash)}")

    SEED.write_text(
        "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in kept + items),
        encoding="utf-8",
    )
    verb = f"replaced {replaced} and merged" if replaced else "merged"
    print(f"{verb} into {SEED.relative_to(ROOT)}: {len(existing)} -> "
          f"{len(kept) + len(items)} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
