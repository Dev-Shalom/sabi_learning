#!/usr/bin/env python
"""Generate the Chemistry slice of the golden set.

Same shape as `build_physics_golden.py`, and for the same reason: a subject
with no golden items is a subject nobody is measuring, and Chemistry does not
count as switched on until it has a slice of its own.

The answerable items are derived from the worked examples, so the expected
answer in the golden set and the answer in the corpus cannot drift apart --
`expected_answer` is read out of the example file itself rather than retyped,
and `tests/test_chemistry_corpus.py` independently checks the chemistry.

The unanswerable items are hand-written, because what a syllabus *excludes* is
a judgement rather than a calculation. Each one quotes the `Not on this
syllabus` section that should ground the refusal, so a failure says which
document needs work rather than only that the confidence was low.

    python tools/build_chemistry_golden.py          # writes the slice
    python tools/build_chemistry_golden.py --merge  # folds it into seed.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "eval" / "golden" / "seed.jsonl"
SLICE = ROOT / "eval" / "golden" / "chemistry.jsonl"
EXAMPLES = ROOT / "corpus" / "chemistry" / "examples"
SYLLABUS = ROOT / "corpus" / "chemistry" / "syllabus"

SUBJECT = "Chemistry"
BOARD = "WAEC"
PREFIX = "c"


def item(**kw) -> dict:
    """A golden item with the keys in the same order as the existing files."""
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
# test is a string match against the corpus's own words and proves nothing.
#
# The third field is `expected_value`: the value the harness looks for in the
# prose, and always one the worked example actually computes. It is None where
# a bare value comparison would be meaningless -- a formula, a half-equation,
# an oxidation number, a Kc expression. Those items are still scored on
# retrieval, citations and the judge's reading of `expected_answer`; they are
# simply not scored on "does this paragraph contain the string 40".
ASKED = {
    "chm-ex-01-moles-from-mass": (
        "how many moles are in 10 g of NaOH and how many particles is that",
        "0.25", "Mole concept", "easy"),
    "chm-ex-02-moles-from-gas-volume": (
        "i have 5.6 dm3 of carbon dioxide at s.t.p, what mass of gas is that",
        "11", "Mole concept", "easy"),
    "chm-ex-03-empirical-formula": (
        "an oxide of sulphur is 40% sulphur and 60% oxygen by mass, work out "
        "its empirical formula",
        None, "Formulae", "medium"),
    "chm-ex-04-molecular-formula": (
        "the empirical formula is CH2 and the relative molecular mass is 56, "
        "what is the molecular formula",
        None, "Formulae", "easy"),
    "chm-ex-05-reacting-masses": (
        "if i burn 12 g of magnesium completely in oxygen how much magnesium "
        "oxide do i get",
        "20", "Stoichiometry", "medium"),
    "chm-ex-06-limiting-reactant": (
        "6.5 g of zinc is put into 50 cm3 of 2 mol/dm3 hydrochloric acid, "
        "which reactant runs out first and what volume of hydrogen comes off "
        "at s.t.p",
        "1.12", "Stoichiometry", "hard"),
    "chm-ex-07-concentration-mol-per-dm3": (
        "i dissolved 7.45 g of potassium chloride and made it up to 250 cm3, "
        "what is the concentration in mol/dm3",
        "0.4", "Solutions", "easy"),
    "chm-ex-08-concentration-g-per-dm3": (
        "how do i change a 0.5 mol/dm3 solution of H2SO4 into g/dm3",
        "49", "Solutions", "medium"),
    "chm-ex-09-dilution": (
        "if i water down 50 cm3 of 0.8 mol/dm3 hydrochloric acid until it is "
        "200 cm3, what is the new concentration",
        "0.2", "Solutions", "easy"),
    "chm-ex-10-titration": (
        "in a titration 25 cm3 of 0.1 mol/dm3 Na2CO3 needed 20 cm3 of "
        "hydrochloric acid to neutralise it, find the concentration of the acid",
        "0.25", "Volumetric analysis", "hard"),
    "chm-ex-11-percentage-purity": (
        "heating 6.25 g of impure limestone gave off 1.12 dm3 of carbon "
        "dioxide at s.t.p, how pure was the sample",
        "80", "Stoichiometry", "hard"),
    "chm-ex-12-percentage-yield": (
        "50 g of calcium trioxocarbonate(IV) was heated and only 21 g of "
        "calcium oxide came out, what is the percentage yield",
        "75", "Stoichiometry", "medium"),
    "chm-ex-13-oxidation-number": (
        "what is the oxidation number of chromium in K2Cr2O7 and of nitrogen "
        "in the ammonium ion",
        None, "Redox", "medium"),
    "chm-ex-14-redox-half-equation": (
        "how do i balance the half equation for Cr2O7 2- being reduced to "
        "Cr3+ in acid",
        None, "Redox", "hard"),
    "chm-ex-15-electrolysis-faraday": (
        "a current of 5 A runs for 32 minutes 10 seconds through copper(II) "
        "tetraoxosulphate(VI) solution, what mass of copper plates out",
        "3.2", "Electrolysis", "hard"),
    "chm-ex-16-heat-of-reaction": (
        "mixing 100 cm3 of 1 mol/dm3 HCl with 100 cm3 of 1 mol/dm3 NaOH "
        "raised the temperature by 6.8 degrees, what is the heat of "
        "neutralisation",
        "57.12", "Energy changes", "hard"),
    "chm-ex-17-rate-of-reaction": (
        "a reactant drops from 0.5 to 0.2 mol/dm3 in 60 seconds, what is the "
        "average rate",
        "0.005", "Rates of reaction", "easy"),
    "chm-ex-18-equilibrium-constant": (
        "for 2SO2 + O2 giving 2SO3 at equilibrium with 0.2 mol/dm3 SO2, 0.1 "
        "mol/dm3 O2 and 0.4 mol/dm3 SO3, how do i write Kc and what is it",
        None, "Chemical equilibrium", "hard"),
    "chm-ex-19-relative-molecular-mass": (
        "work out the relative molecular mass of Ca(OH)2 and of the hydrated "
        "salt CuSO4.5H2O",
        "250", "Mole concept", "easy"),
    "chm-ex-20-general-gas-law": (
        "380 cm3 of gas was collected at 27 degrees and 800 mmHg, what volume "
        "would it be at s.t.p",
        "364", "Gas laws", "medium"),
    "chm-ex-21-homologous-series-formula": (
        "an alkane has a relative molecular mass of 58 and an alkyne has one "
        "of 40, what are they",
        None, "Hydrocarbons", "medium"),
}


# The syllabus document covering the same ground as each worked example.
#
# Both count as a hit, because `score_retrieval` treats `expected_docs` as
# "any of these". The two measurements are deliberately separate: recall asks
# whether relevant material was found at all, and the value check asks whether
# the answer is right. A conceptual question -- "how do i write Kc" -- is
# better served by the syllabus text than by one worked example of it, and
# scoring that as a miss would be measuring the wrong thing.
#
# Each entry is checked at build time against the `syllabus_section` in the
# worked example's own front matter, so the two cannot drift apart either.
COVERS = {
    "chm-ex-01-moles-from-mass": "chm-syl-b01-mole-concept-stoichiometry",
    "chm-ex-02-moles-from-gas-volume": "chm-syl-b01-mole-concept-stoichiometry",
    "chm-ex-03-empirical-formula": "chm-syl-b01-mole-concept-stoichiometry",
    "chm-ex-04-molecular-formula": "chm-syl-b01-mole-concept-stoichiometry",
    "chm-ex-05-reacting-masses": "chm-syl-b01-mole-concept-stoichiometry",
    "chm-ex-06-limiting-reactant": "chm-syl-b01-mole-concept-stoichiometry",
    "chm-ex-07-concentration-mol-per-dm3": "chm-syl-b03-solutions-and-solubility",
    "chm-ex-08-concentration-g-per-dm3": "chm-syl-b03-solutions-and-solubility",
    "chm-ex-09-dilution": "chm-syl-b03-solutions-and-solubility",
    "chm-ex-10-titration": "chm-syl-b04-volumetric-analysis",
    "chm-ex-11-percentage-purity": "chm-syl-b01-mole-concept-stoichiometry",
    "chm-ex-12-percentage-yield": "chm-syl-b01-mole-concept-stoichiometry",
    "chm-ex-13-oxidation-number": "chm-syl-c02-oxidation-reduction",
    "chm-ex-14-redox-half-equation": "chm-syl-c02-oxidation-reduction",
    "chm-ex-15-electrolysis-faraday": "chm-syl-c03-electrolysis",
    "chm-ex-16-heat-of-reaction": "chm-syl-c04-energy-changes",
    "chm-ex-17-rate-of-reaction": "chm-syl-c05-rates-of-reaction",
    "chm-ex-18-equilibrium-constant": "chm-syl-c06-chemical-equilibrium",
    "chm-ex-19-relative-molecular-mass": "chm-syl-b01-mole-concept-stoichiometry",
    "chm-ex-20-general-gas-law": "chm-syl-b02-states-of-matter-gas-laws",
    "chm-ex-21-homologous-series-formula": "chm-syl-e01-alkanes-alkenes",
}


def _front_matter_field(body: str, key: str) -> str | None:
    m = re.search(rf"^{key}:\s*(.+)$", body, re.M)
    return m.group(1).strip() if m else None


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
        answer = m.group(1).strip()

        # Never invent a value: whatever the item claims must be something the
        # example's own answer line says.
        if value is not None and value.lstrip("-") not in answer.replace(",", ""):
            raise SystemExit(
                f"{doc_id}: expected_value {value!r} is not in the worked "
                f"example's answer {answer!r}"
            )

        covers = COVERS[doc_id]
        if not (SYLLABUS / f"{covers}.md").is_file():
            raise SystemExit(f"{doc_id} covered by a missing syllabus doc: {covers}")
        # Front matter says "B1"; the document is `chm-syl-b01-...`.
        section = _front_matter_field(body, "syllabus_section") or ""
        sm = re.fullmatch(r"([A-Za-z])(\d+)", section)
        if sm and f"chm-syl-{sm.group(1).lower()}{int(sm.group(2)):02d}-" not in covers:
            raise SystemExit(
                f"{doc_id} is tagged syllabus_section {section} but COVERS "
                f"points at {covers}"
            )

        out.append(item(
            slug=f"{PREFIX}-{i:03d}",
            question=question,
            expected_docs=[doc_id, covers],
            expected_value=value,
            expected_answer=answer,
            topic=topic,
            difficulty=difficulty,
        ))
    return out


# Hand-written, and each one is drawn from the `Not on this syllabus` section
# of a real Chemistry syllabus document -- the note names it, so a failure
# points at the document whose exclusion text did not do its job.
UNANSWERABLE = [
    ("Use the initial rate data to find the order of the reaction with respect "
     "to each reactant and the value of the rate constant",
     "out_of_syllabus", "Rates of reaction",
     "CHM C5 excludes rate equations, the order of a reaction and the rate "
     "constant."),
    ("Use PV = nRT with R = 8.314 to find the number of moles in the flask",
     "out_of_syllabus", "Gas laws",
     "CHM B2 and CHM B1 both exclude the ideal gas equation PV = nRT with the "
     "gas constant."),
    ("Explain why copper(II) complex ions are blue using crystal field "
     "splitting of the d orbitals",
     "out_of_syllabus", "Transition metals",
     "CHM D2 excludes complex ion theory and the explanation of their colour "
     "by crystal-field splitting; CHM A3 excludes ligand-field theory."),
    ("Draw the curly arrow mechanism for the electrophilic addition of HBr to "
     "ethene and explain carbocation stability",
     "out_of_syllabus", "Organic mechanisms",
     "CHM E1 excludes electrophilic addition mechanisms with curly arrows and "
     "carbocation stability."),
    ("Calculate the pH of a buffer made from ethanoic acid and sodium "
     "ethanoate using the Henderson-Hasselbalch equation",
     "out_of_syllabus", "Acids, bases and salts",
     "CHM C1 excludes buffers treated quantitatively by "
     "Henderson-Hasselbalch, and Ka used to calculate the pH of a weak acid."),
    ("Where do the lanthanides and actinides sit in the periodic table and "
     "what is their chemistry",
     "out_of_syllabus", "Periodic table",
     "CHM A4 excludes the lanthanides and actinides."),
    ("How do I read an infrared spectrum to tell an alkene from an alkane",
     "out_of_syllabus", "Spectroscopy",
     "CHM E1 excludes infrared and NMR spectra; CHM A0 excludes spectroscopy "
     "of any kind."),
    # Out of subject, written like u-016: numerical and plausible-looking,
    # which is exactly why it is a good trap. Chemistry is the scope; this
    # belongs to Physics.
    ("A 2 kg block is lifted through 5 m. Calculate the work done against "
     "gravity, taking g as 10 m/s2.",
     "out_of_subject", "Work and energy",
     "Physics, not Chemistry. Numerical and plausible-looking, which is what "
     "makes it a good test of the scope."),
    ("Solve the simultaneous equations 3x + 2y = 16 and x - y = 2.",
     "out_of_subject", "Simultaneous equations",
     "Mathematics asked under the Chemistry scope; the Chemistry corpus has "
     "nothing to ground it and must not answer from general knowledge."),
]


def unanswerable_items() -> list[dict]:
    start = len(ASKED) + 1
    return [
        item(
            slug=f"{PREFIX}-{start + i:03d}",
            question=question,
            answerable=False,
            unanswerable_kind=kind,
            topic=topic,
            difficulty="n/a",
            notes=note,
        )
        for i, (question, kind, topic, note) in enumerate(UNANSWERABLE)
    ]


def _existing_slugs() -> set[str]:
    """Every slug already claimed by a golden file, so the slice cannot clash."""
    seen: set[str] = set()
    for path in sorted((ROOT / "eval" / "golden").glob("*.jsonl")):
        if path == SLICE:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen.add(json.loads(line)["slug"])
    return seen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge", action="store_true",
                    help="append the slice to eval/golden/seed.jsonl")
    args = ap.parse_args()

    items = answerable_items() + unanswerable_items()
    slugs = [i["slug"] for i in items]
    if len(set(slugs)) != len(slugs):
        raise SystemExit("duplicate slugs in the generated slice")

    clash = _existing_slugs() & set(slugs)
    if clash:
        raise SystemExit(f"slugs already used by another slice: {sorted(clash)}")

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
    # Replace any earlier Chemistry slice rather than refusing. This file is
    # generated, so running it twice should converge on the same result -- and
    # while the slice is being tuned it will be run many times.
    kept = [e for e in existing if not e["slug"].startswith(f"{PREFIX}-")]
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
