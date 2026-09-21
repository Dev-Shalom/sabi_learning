"""The Chemistry corpus, checked by something that did not write it.

`tools/build_chemistry_examples.py` computes each answer rather than typing
it, which removes one class of mistake. It does not remove the other, and in
Chemistry the other is worse: a wrong molar mass, a mis-balanced equation or
the wrong number of electrons gives an answer that is arithmetically
consistent with itself and chemically wrong. That is the single output this
product most needs not to produce.

So this file states the chemistry again, from scratch, and recomputes every
quantity from the givens. It shares no code with the generator -- not the
formatter, not the relative atomic masses, not the constants. If the two ever
disagree, one of them is wrong and the build stops until somebody says which.

Modelled on tests/test_physics_corpus.py, which does the same job for Physics.

Constants restated here rather than imported: molar gas volume 22.4 dm3/mol at
s.t.p., the Faraday constant 96500 C/mol, the Avogadro constant 6.02 x 10^23
per mole, and the specific heat capacity of water 4200 J/kg/K.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sabi.corpus.loader import load_dir

CHEMISTRY = Path(__file__).resolve().parent.parent / "corpus" / "chemistry"

# Same shape a citation must take, from sabi/answer/generator.py. A locator
# that does not match is stripped from an answer, and if none survives the
# answer is discarded -- so a malformed one here is a silent failure later.
CITATION = re.compile(r"^[A-Z]{2,3}\s?[A-Z]?\d{1,3}(?:\.\d+)?$")

MIN_EXCLUSION_SECTIONS = 12

# Constants, restated independently of the generator.
MOLAR_VOLUME = 22.4
FARADAY = 96500.0
AVOGADRO_MANTISSA = 6.02
SHC_WATER = 4200.0

# Relative atomic masses, restated independently of the generator.
RAM = {
    "H": 1.0, "C": 12.0, "N": 14.0, "O": 16.0, "Na": 23.0, "Mg": 24.0,
    "S": 32.0, "Cl": 35.5, "K": 39.0, "Ca": 40.0, "Fe": 56.0, "Cu": 64.0,
    "Zn": 65.0, "Ag": 108.0,
}


@pytest.fixture(scope="module")
def docs():
    loaded = load_dir(CHEMISTRY)
    assert loaded, "no Chemistry documents found"
    return loaded


@pytest.fixture(scope="module")
def by_id(docs):
    return {d.doc_id: d for d in docs}


# ------------------------------------------------------------------ shape


def test_every_document_declares_its_syllabus(docs):
    """Explicit, not defaulted.

    The loader defaults `subject` to Mathematics when it is absent, which is
    how a part-written Physics corpus was once ingested as though it were
    Mathematics. These say what they are.
    """
    for d in docs:
        assert d.meta.get("subject") == "Chemistry", (
            f"{d.doc_id} does not say Chemistry"
        )
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
    """Without these, Chemistry has no grounded refusals at all.

    A refusal that can cite the line saying a topic belongs to another course
    is a different thing from one that fires because a score fell below a
    number.
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


def test_constants_are_stated_where_they_are_used(docs):
    """A constant a student cannot see is a number they cannot check.

    Each rule is (trigger word, the values any one of which would satisfy it).
    s.t.p. takes either form: a document that converts between moles and a gas
    volume must state 22.4 dm3/mol, and one that merely corrects a volume to
    standard conditions must say what those conditions are.
    """
    triggers = [
        ("s.t.p.", ("22.4", "273")),
        ("faraday", ("96500",)),
        ("avogadro", ("6.02",)),
        ("specific heat capacity", ("4200", "4.2")),
    ]
    for d in docs:
        if d.attribution != "worked_example":
            continue
        body = d.body.lower()
        for word, constants in triggers:
            if word in body:
                assert any(c in d.body for c in constants), (
                    f"{d.doc_id} mentions {word} without stating any of "
                    f"{constants}"
                )


# ----------------------------------------------------------- the chemistry
#
# Each entry recomputes the quantity from first principles and names the
# substrings the document's answer line must contain. Nothing here reads the
# generator.


def _answer(doc) -> str:
    m = re.search(r"\*\*Answer:(.+?)\*\*", doc.body, re.S)
    assert m, f"{doc.doc_id} has no answer line"
    return m.group(1).strip()


def _near(value: float, dp: int = 2) -> str:
    r = round(value, dp)
    return str(int(r)) if r == int(r) else f"{r:.{dp}f}".rstrip("0").rstrip(".")


def _mm(*parts: tuple[str, int]) -> float:
    """Molar mass from (element, count) pairs, summed here from scratch."""
    return sum(RAM[sym] * count for sym, count in parts)


# -- 1. moles and particles from a mass of NaOH -----------------------------
_mm_naoh = _mm(("Na", 1), ("O", 1), ("H", 1))                 # 40
_mol_naoh = 10.0 / _mm_naoh                                   # 0.25
_units_naoh = _mol_naoh * AVOGADRO_MANTISSA                   # 1.505 x 10^23

# -- 2. moles and mass from a gas volume at s.t.p. --------------------------
_mol_co2 = 5.6 / MOLAR_VOLUME                                 # 0.25
_mass_co2 = _mol_co2 * _mm(("C", 1), ("O", 2))                # 11 g

# -- 3. empirical formula from 40% S, 60% O ---------------------------------
_r_s = (40.0 / RAM["S"])
_r_o = (60.0 / RAM["O"])
_small = min(_r_s, _r_o)
_emp = f"S{'' if round(_r_s / _small) == 1 else round(_r_s / _small)}" \
       f"O{round(_r_o / _small)}"                             # SO3

# -- 4. molecular formula from CH2 and RMM 56 -------------------------------
_mult = 56.0 / _mm(("C", 1), ("H", 2))                        # 4
_molf = f"C{round(_mult)}H{round(2 * _mult)}"                 # C4H8

# -- 5. reacting masses, 2Mg + O2 -> 2MgO -----------------------------------
_mass_mgo = (12.0 / RAM["Mg"]) * _mm(("Mg", 1), ("O", 1))     # 20 g

# -- 6. limiting reactant, Zn + 2HCl -> ZnCl2 + H2 --------------------------
_mol_zn = 6.5 / RAM["Zn"]                                     # 0.1
_mol_hcl6 = 2.0 * (50.0 / 1000)                               # 0.1
_limiting = "hydrochloric acid" if (_mol_hcl6 / 2) < (_mol_zn / 1) else "zinc"
_vol_h2 = min(_mol_zn / 1, _mol_hcl6 / 2) * MOLAR_VOLUME      # 1.12 dm3

# -- 7. molar concentration of KCl ------------------------------------------
_conc_kcl = (7.45 / _mm(("K", 1), ("Cl", 1))) / (250.0 / 1000)   # 0.4

# -- 8. mass and molar concentration ----------------------------------------
_gdm3_h2so4 = 0.5 * _mm(("H", 2), ("S", 1), ("O", 4))         # 49
_moldm3_naoh = 8.0 / _mm(("Na", 1), ("O", 1), ("H", 1))       # 0.2

# -- 9. dilution -------------------------------------------------------------
_c2_dil = 0.8 * 50.0 / 200.0                                  # 0.2

# -- 10. titration, Na2CO3 + 2HCl -> 2NaCl + H2O + CO2 ----------------------
_mol_na2co3 = 0.100 * (25.0 / 1000)
_conc_hcl10 = (2 * _mol_na2co3) / (20.0 / 1000)               # 0.25
_gdm3_hcl10 = _conc_hcl10 * _mm(("H", 1), ("Cl", 1))          # 9.125

# -- 11. percentage purity ---------------------------------------------------
_mass_pure = (1.12 / MOLAR_VOLUME) * _mm(("Ca", 1), ("C", 1), ("O", 3))   # 5 g
_purity = _mass_pure / 6.25 * 100                             # 80

# -- 12. percentage yield ----------------------------------------------------
_theoretical_cao = (50.0 / _mm(("Ca", 1), ("C", 1), ("O", 3))) * _mm(
    ("Ca", 1), ("O", 1)
)                                                             # 28 g
_yield = 21.0 / _theoretical_cao * 100                        # 75

# -- 13. oxidation numbers ---------------------------------------------------
# K2Cr2O7 is neutral: 2(+1) + 2x + 7(-2) = 0
_ox_cr = (0 - 2 * 1 - 7 * -2) / 2                             # +6
# NH4+ carries +1: y + 4(+1) = +1
_ox_n = 1 - 4 * 1                                             # -3

# -- 14. half-equation for Cr2O7 2- -> Cr3+ in acid -------------------------
# Balance O with water, H with H+, then charge with electrons.
_water = 7                                    # seven O in Cr2O7 2-
_hplus = 2 * _water                           # two H per water
_electrons = (-2 + _hplus) - (2 * 3)          # left charge minus right charge

# -- 15. electrolysis of CuSO4(aq), Cu2+ + 2e- -> Cu ------------------------
_q = 5.0 * (32 * 60 + 10)                                     # 9650 C
_mass_cu = (_q / FARADAY / 2) * RAM["Cu"]                     # 3.2 g

# -- 16. heat of neutralisation ---------------------------------------------
_mass_kg = (100.0 + 100.0) / 1000                             # 0.2 kg
_heat_q = _mass_kg * SHC_WATER * 6.8                          # 5712 J
_mol_water = 1.0 * (100.0 / 1000)                             # 0.1 mol
_dh_kj = -_heat_q / _mol_water / 1000                         # -57.12

# -- 17. average rate --------------------------------------------------------
_rate = (0.50 - 0.20) / 60.0                                  # 0.005

# -- 18. equilibrium constant for 2SO2 + O2 <=> 2SO3 ------------------------
_kc = (0.40 ** 2) / ((0.20 ** 2) * 0.10)                      # 40

# -- 19. relative molecular masses -------------------------------------------
_rmm_caoh2 = RAM["Ca"] + 2 * (RAM["O"] + RAM["H"])            # 74
_rmm_hydrate = _mm(("Cu", 1), ("S", 1), ("O", 4)) + 5 * _mm(("H", 2), ("O", 1))

# -- 20. correcting a gas volume to s.t.p. ----------------------------------
_v2 = 800.0 * 380.0 * 273.0 / ((27.0 + 273.0) * 760.0)        # 364 cm3

# -- 21. homologous series ---------------------------------------------------
_n_alkane = (58.0 - 2) / 14                                   # 4
_alkane = f"C{round(_n_alkane)}H{round(2 * _n_alkane + 2)}"   # C4H10
_n_alkyne = (40.0 + 2) / 14                                   # 3
_alkyne = f"C{round(_n_alkyne)}H{round(2 * _n_alkyne - 2)}"   # C3H4


CHECKS: list[tuple[str, str, list[str]]] = [
    ("chm-ex-01-moles-from-mass", "n = m/M, then x the Avogadro constant",
     [f"{_near(_mol_naoh, 2)} mol", f"{_near(_units_naoh, 3)} x 10^23"]),
    ("chm-ex-02-moles-from-gas-volume", "n = V/22.4 at s.t.p., m = nM",
     [f"{_near(_mol_co2, 2)} mol", f"{_near(_mass_co2, 2)} g"]),
    ("chm-ex-03-empirical-formula", "divide % by RAM, then by the smallest",
     [_emp]),
    ("chm-ex-04-molecular-formula", "RMM / empirical formula mass",
     [_molf]),
    ("chm-ex-05-reacting-masses", "2Mg + O2 -> 2MgO, 1:1 in moles",
     [f"{_near(_mass_mgo, 2)} g"]),
    ("chm-ex-06-limiting-reactant", "divide moles by coefficients; V = n x 22.4",
     [_limiting, f"{_near(_vol_h2, 2)} dm3"]),
    ("chm-ex-07-concentration-mol-per-dm3", "c = (m/M) / (V/1000)",
     [f"{_near(_conc_kcl, 2)} mol/dm3"]),
    ("chm-ex-08-concentration-g-per-dm3", "g/dm3 = mol/dm3 x M, and back",
     [f"{_near(_gdm3_h2so4, 2)} g/dm3", f"{_near(_moldm3_naoh, 2)} mol/dm3"]),
    ("chm-ex-09-dilution", "C1V1 = C2V2",
     [f"{_near(_c2_dil, 2)} mol/dm3"]),
    ("chm-ex-10-titration", "mole ratio 1 Na2CO3 to 2 HCl",
     [f"{_near(_conc_hcl10, 2)} mol/dm3", f"{_near(_gdm3_hcl10, 3)} g/dm3"]),
    ("chm-ex-11-percentage-purity", "mass of pure CaCO3 from the CO2 collected",
     [f"{_near(_purity, 2)} per cent"]),
    ("chm-ex-12-percentage-yield", "actual / theoretical x 100",
     [f"{_near(_theoretical_cao, 2)} g", f"{_near(_yield, 2)} per cent"]),
    ("chm-ex-13-oxidation-number", "oxidation numbers sum to the charge",
     [f"+{_near(_ox_cr, 2)}", _near(_ox_n, 2)]),
    ("chm-ex-14-redox-half-equation", "O with water, H with H+, charge with e-",
     [f"{_hplus}H+", f"{_electrons}e-", f"{_water}H2O", "2Cr3+"]),
    ("chm-ex-15-electrolysis-faraday", "Q = It, n(e-) = Q/96500, Cu needs 2e-",
     [f"{_near(_mass_cu, 2)} g"]),
    ("chm-ex-16-heat-of-reaction", "Q = mc x dtheta, then per mole of water",
     [f"{_near(_heat_q, 2)} J", f"{_near(_dh_kj, 2)} kJ/mol"]),
    ("chm-ex-17-rate-of-reaction", "rate = change in concentration / time",
     [f"{_near(_rate, 4)} mol/dm3 per second"]),
    ("chm-ex-18-equilibrium-constant", "Kc = [SO3]^2 / ([SO2]^2 x [O2])",
     [f"{_near(_kc, 2)} dm3/mol"]),
    ("chm-ex-19-relative-molecular-mass", "sum the relative atomic masses",
     [f"(a) {_near(_rmm_caoh2, 2)}", f"(b) {_near(_rmm_hydrate, 2)}"]),
    ("chm-ex-20-general-gas-law", "P1V1/T1 = P2V2/T2 with T in kelvin",
     [f"{_near(_v2, 2)} cm3"]),
    ("chm-ex-21-homologous-series-formula", "14n + 2 for CnH2n+2, 14n - 2 for CnH2n-2",
     [_alkane, _alkyne]),
]


@pytest.mark.parametrize("doc_id,what,expected", CHECKS, ids=[c[0] for c in CHECKS])
def test_the_stated_answer_is_the_right_one(by_id, doc_id, what, expected):
    """Recompute the chemistry and check the document agrees.

    The check is on the answer line specifically, not anywhere in the body: a
    number that appears only in the working is not what a student takes away.
    """
    doc = by_id.get(doc_id)
    assert doc is not None, f"{doc_id} is missing from the corpus"
    answer = _answer(doc)

    for item in expected:
        assert item in answer, (
            f"{doc_id} ({what}): recomputing gives {item!r}, which does not "
            f"appear in the stated answer {answer!r}"
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


def test_the_checks_are_not_vacuous():
    """Guard the guard.

    Every expected substring must be non-empty, and the numeric ones must be
    long enough that they could not match by accident. A check that passes
    against any answer is worse than no check, because it reads as coverage.
    """
    for doc_id, _what, expected in CHECKS:
        assert expected, f"{doc_id} has no expected values"
        for item in expected:
            assert len(item) >= 2, f"{doc_id} has a trivially short check {item!r}"


def test_every_syllabus_section_cited_by_an_example_exists(docs):
    """An example filed under a section no syllabus document declares is a
    citation pointing at nothing."""
    sections = {
        d.syllabus_section for d in docs if d.attribution == "syllabus"
    }
    for d in docs:
        if d.attribution != "worked_example":
            continue
        assert d.syllabus_section in sections, (
            f"{d.doc_id} claims syllabus_section {d.syllabus_section!r}, which "
            f"no Chemistry syllabus document declares"
        )
