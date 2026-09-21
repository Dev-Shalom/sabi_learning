#!/usr/bin/env python
"""Generate the Chemistry worked examples, with every answer computed.

Same discipline as `tools/build_physics_examples.py`, and for the same reason.
The product's claim is that it is not confidently wrong, and a worked example
with a slip in its final line is exactly the kind of wrong that survives
proofreading. So no number in the output is typed: each example states its
givens, the arithmetic is done here, and the stated answer is formatted from
the computed value.

Chemistry adds a second failure mode that Physics mostly does not have. An
answer can be arithmetically consistent and still chemically wrong -- a
mis-balanced equation, a wrong molar mass, the wrong number of electrons. So
`tests/test_chemistry_corpus.py` restates the chemistry from scratch and
recomputes every quantity from the markdown, sharing no code with this file.

    python tools/build_chemistry_examples.py

Conventions, taken from corpus/chemistry/syllabus/ so the examples read like
the documents they sit beside:

* WAEC (IUPAC stock) nomenclature -- carbon(IV) oxide, tetraoxosulphate(VI)
  acid, calcium trioxocarbonate(IV).
* Formulae written in plain ASCII, as the syllabus documents write them:
  H2SO4, SO4 2-, Cr2O7 2-. No subscript characters.
* Constants: molar gas volume 22.4 dm3/mol at s.t.p.; the Faraday constant
  96500 C/mol; the Avogadro constant 6.02 x 10^23 per mole; the specific heat
  capacity of water 4200 J/kg/K, which is 4.2 J/g/K. Every constant used is
  stated in the question or in the working.
* Relative atomic masses are quoted in the question that needs them.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "corpus" / "chemistry" / "examples"

# Constants, named once. Anything that uses one also states it in its text.
MOLAR_VOLUME = 22.4      # dm3 per mole at s.t.p.
FARADAY = 96500.0        # coulombs per mole of electrons
AVOGADRO_MANTISSA = 6.02  # x 10^23 per mole
C_WATER = 4200.0         # J per kg per K

# Relative atomic masses used anywhere in this file.
H, C, N, O = 1.0, 12.0, 14.0, 16.0
NA, MG, S, CL = 23.0, 24.0, 32.0, 35.5
K, CA, FE, CU, ZN, AG = 39.0, 40.0, 56.0, 64.0, 65.0, 108.0


def n(value: float, dp: int = 2) -> str:
    """A number as a student would write it: no trailing zeros, no -0."""
    rounded = round(value + 0.0, dp)
    if rounded == int(rounded):
        return str(int(rounded))
    text = f"{rounded:.{dp}f}".rstrip("0").rstrip(".")
    return text if text != "-0" else "0"


def doc(
    *,
    num: int,
    slug: str,
    title: str,
    topic: str,
    subtopic: str,
    section: str,
    question: str,
    steps: list[str],
    answer: str,
) -> tuple[str, str]:
    """One worked example, in the same shape as the Physics corpus.

    `title` must not contain a colon. An unquoted colon in a YAML scalar is
    how a half-written Chemistry document once broke `sabi ingest` for every
    subject, so the constraint is enforced here rather than remembered.
    """
    if ":" in title:
        raise ValueError(
            f"title {title!r} contains a colon; it would have to be quoted, so "
            "rewrite it without one"
        )
    body = "\n".join(f"{i}. {line}" for i, line in enumerate(steps, start=1))
    text = f"""---
doc_id: chm-ex-{num:02d}-{slug}
title: {title}
source: Sabi worked example, WAEC Paper 2 style
attribution: worked_example
topic: {topic}
subtopic: {subtopic}
syllabus_section: {section}
exam_board: WAEC
subject: Chemistry
level: SS3
locator: CEX {num}
---

## Question

{question}

## Solution

{body}

**Answer: {answer}**
"""
    return f"chm-ex-{num:02d}-{slug}.md", text


QUANT = "Quantitative chemistry"
MOLE = "Mole concept and stoichiometry"
REACTIONS = "Chemical reactions"

EXAMPLES: list[tuple[str, str]] = []


# ------------------------------------------------------- 1. moles from mass
m_naoh, mm_naoh = 10.0, NA + O + H
mol_naoh = m_naoh / mm_naoh
units_naoh = mol_naoh * AVOGADRO_MANTISSA          # x 10^23
EXAMPLES.append(doc(
    num=1, slug="moles-from-mass", title="Moles and particles from a mass",
    topic=QUANT, subtopic=MOLE, section="B1",
    question=(
        f"Calculate (a) the number of moles in {n(m_naoh)} g of sodium "
        "hydroxide, NaOH, and (b) the number of formula units it contains. "
        f"[H = {n(H)}, O = {n(O)}, Na = {n(NA)}; Avogadro constant = "
        f"{n(AVOGADRO_MANTISSA)} x 10^23 per mole]"
    ),
    steps=[
        "First find the molar mass by adding the relative atomic masses of the "
        "atoms in the formula.",
        f"Molar mass of NaOH = {n(NA)} + {n(O)} + {n(H)} = {n(mm_naoh)} g/mol.",
        "Part (a). Number of moles = mass in grams / molar mass in g/mol.",
        f"Number of moles = {n(m_naoh)} / {n(mm_naoh)} = {n(mol_naoh)} mol.",
        "Part (b). One mole contains the Avogadro number of formula units, "
        f"{n(AVOGADRO_MANTISSA)} x 10^23 per mole, so multiply the moles by it.",
        f"Formula units = {n(mol_naoh)} x {n(AVOGADRO_MANTISSA)} x 10^23 = "
        f"{n(units_naoh, 3)} x 10^23.",
        "NaOH is ionic, so these are formula units, not molecules. Each one "
        "supplies one Na+ ion and one OH- ion in solution.",
    ],
    answer=f"(a) {n(mol_naoh)} mol  (b) {n(units_naoh, 3)} x 10^23 formula units",
))


# ------------------------------------------- 2. moles from gas volume at s.t.p.
v_co2, mm_co2 = 5.6, C + 2 * O
mol_co2 = v_co2 / MOLAR_VOLUME
mass_co2 = mol_co2 * mm_co2
EXAMPLES.append(doc(
    num=2, slug="moles-from-gas-volume", title="Moles and mass from a gas volume",
    topic=QUANT, subtopic=MOLE, section="B1",
    question=(
        f"A sample of carbon(IV) oxide, CO2, occupies {n(v_co2)} dm3 at s.t.p. "
        "Calculate (a) the number of moles present, (b) the mass of the sample. "
        f"[C = {n(C)}, O = {n(O)}; molar volume of a gas at s.t.p. = "
        f"{n(MOLAR_VOLUME)} dm3/mol]"
    ),
    steps=[
        "Part (a). At s.t.p. one mole of any gas occupies "
        f"{n(MOLAR_VOLUME)} dm3, so number of moles = volume in dm3 / "
        f"{n(MOLAR_VOLUME)}.",
        f"Number of moles = {n(v_co2)} / {n(MOLAR_VOLUME)} = {n(mol_co2)} mol.",
        "Part (b). Mass = number of moles x molar mass.",
        f"Molar mass of CO2 = {n(C)} + (2 x {n(O)}) = {n(mm_co2)} g/mol.",
        f"Mass = {n(mol_co2)} x {n(mm_co2)} = {n(mass_co2)} g.",
        "The molar volume applies only at s.t.p., which is 273 K and 760 mmHg. "
        "A volume measured at other conditions must be corrected first.",
    ],
    answer=f"(a) {n(mol_co2)} mol  (b) {n(mass_co2)} g",
))


# ------------------------------------------------------ 3. empirical formula
pc_s, pc_o = 40.0, 60.0
mol_s_e = pc_s / S
mol_o_e = pc_o / O
smallest_e = min(mol_s_e, mol_o_e)
ratio_s = mol_s_e / smallest_e
ratio_o = mol_o_e / smallest_e
emp_formula = f"S{'' if round(ratio_s) == 1 else round(ratio_s)}O{round(ratio_o)}"
EXAMPLES.append(doc(
    num=3, slug="empirical-formula", title="Empirical formula from percentage composition",
    topic=QUANT, subtopic=MOLE, section="B1",
    question=(
        f"An oxide of sulphur contains {n(pc_s)} per cent sulphur and "
        f"{n(pc_o)} per cent oxygen by mass. Determine its empirical formula. "
        f"[O = {n(O)}, S = {n(S)}]"
    ),
    steps=[
        "Take 100 g of the compound, so each percentage is a mass in grams.",
        "Divide each mass by the relative atomic mass of that element to get "
        "the number of moles of atoms.",
        f"Sulphur: {n(pc_s)} / {n(S)} = {n(mol_s_e)} mol of atoms.",
        f"Oxygen: {n(pc_o)} / {n(O)} = {n(mol_o_e)} mol of atoms.",
        f"Divide both by the smaller of the two, {n(smallest_e)}, to get the "
        "simplest ratio.",
        f"Sulphur: {n(mol_s_e)} / {n(smallest_e)} = {n(ratio_s)}. "
        f"Oxygen: {n(mol_o_e)} / {n(smallest_e)} = {n(ratio_o)}.",
        f"The ratio of sulphur to oxygen atoms is {n(ratio_s)} : {n(ratio_o)}, "
        f"so the empirical formula is {emp_formula}.",
        "Check it. The formula mass is "
        f"{n(S)} + (3 x {n(O)}) = {n(S + 3 * O)}, and "
        f"{n(S)}/{n(S + 3 * O)} x 100 = {n(S / (S + 3 * O) * 100)} per cent "
        "sulphur, which is what the question gave.",
    ],
    answer=emp_formula,
))


# ------------------------------------------------------ 4. molecular formula
emp_ch2_mass = C + 2 * H
rmm_target = 56.0
multiple = rmm_target / emp_ch2_mass
mol_formula = f"C{round(multiple)}H{round(2 * multiple)}"
EXAMPLES.append(doc(
    num=4, slug="molecular-formula", title="Molecular formula from an empirical formula",
    topic=QUANT, subtopic=MOLE, section="B1",
    question=(
        "A hydrocarbon has the empirical formula CH2 and a relative molecular "
        f"mass of {n(rmm_target)}. Determine its molecular formula. "
        f"[H = {n(H)}, C = {n(C)}]"
    ),
    steps=[
        "The molecular formula is always a whole-number multiple of the "
        "empirical formula, so first find the mass of one empirical unit.",
        f"Empirical formula mass of CH2 = {n(C)} + (2 x {n(H)}) = "
        f"{n(emp_ch2_mass)}.",
        "Divide the relative molecular mass by the empirical formula mass to "
        "find the multiple.",
        f"Multiple = {n(rmm_target)} / {n(emp_ch2_mass)} = {n(multiple)}.",
        f"Multiply every subscript in CH2 by {n(multiple)}.",
        f"Molecular formula = {mol_formula}.",
        f"Check it. {mol_formula} has a relative molecular mass of "
        f"({n(round(multiple))} x {n(C)}) + ({n(round(2 * multiple))} x {n(H)}) "
        f"= {n(round(multiple) * C + round(2 * multiple) * H)}, as given. It "
        "fits CnH2n, so it is an alkene.",
    ],
    answer=mol_formula,
))


# -------------------------------------------------- 5. reacting-mass stoichiometry
mass_mg = 12.0
mol_mg = mass_mg / MG
mol_mgo = mol_mg           # 2Mg + O2 -> 2MgO, ratio 2 : 2, so 1 : 1
mm_mgo = MG + O
mass_mgo = mol_mgo * mm_mgo
EXAMPLES.append(doc(
    num=5, slug="reacting-masses", title="Mass of product from a balanced equation",
    topic=QUANT, subtopic=MOLE, section="B1",
    question=(
        f"{n(mass_mg)} g of magnesium is burnt completely in oxygen. Calculate "
        "the mass of magnesium oxide formed. The equation is\n\n"
        "2Mg + O2 -> 2MgO\n\n"
        f"[O = {n(O)}, Mg = {n(MG)}]"
    ),
    steps=[
        "A balanced equation is a statement about moles, so convert the mass "
        "given into moles first.",
        f"Moles of Mg = {n(mass_mg)} / {n(MG)} = {n(mol_mg)} mol.",
        "From the equation, 2 moles of Mg give 2 moles of MgO, a ratio of "
        "1 to 1.",
        f"So moles of MgO formed = {n(mol_mgo)} mol.",
        f"Molar mass of MgO = {n(MG)} + {n(O)} = {n(mm_mgo)} g/mol.",
        f"Mass of MgO = {n(mol_mgo)} x {n(mm_mgo)} = {n(mass_mgo)} g.",
        f"The product is heavier than the magnesium because the "
        f"{n(mass_mgo - mass_mg)} g difference is the oxygen that combined "
        "with it. Mass is conserved overall.",
    ],
    answer=f"{n(mass_mgo)} g of magnesium oxide",
))


# ------------------------------------------------------- 6. limiting reactant
mass_zn, conc_hcl, vol_hcl_cm3 = 6.5, 2.0, 50.0
mol_zn = mass_zn / ZN
mol_hcl = conc_hcl * vol_hcl_cm3 / 1000
share_zn = mol_zn / 1          # coefficient of Zn is 1
share_hcl = mol_hcl / 2        # coefficient of HCl is 2
limiting = "hydrochloric acid" if share_hcl < share_zn else "zinc"
mol_h2 = min(share_zn, share_hcl)
vol_h2 = mol_h2 * MOLAR_VOLUME
EXAMPLES.append(doc(
    num=6, slug="limiting-reactant", title="Limiting reactant and the volume of gas formed",
    topic=QUANT, subtopic=MOLE, section="B1",
    question=(
        f"{n(mass_zn)} g of zinc is added to {n(vol_hcl_cm3)} cm3 of "
        f"{n(conc_hcl)} mol/dm3 hydrochloric acid. The equation is\n\n"
        "Zn + 2HCl -> ZnCl2 + H2\n\n"
        "Determine (a) which reactant is the limiting reactant, (b) the volume "
        "of hydrogen produced at s.t.p. "
        f"[Zn = {n(ZN)}; molar volume of a gas at s.t.p. = {n(MOLAR_VOLUME)} "
        "dm3/mol]"
    ),
    steps=[
        "Part (a). Convert both reactants to moles.",
        f"Moles of Zn = {n(mass_zn)} / {n(ZN)} = {n(mol_zn)} mol.",
        f"Moles of HCl = concentration x volume in dm3 = {n(conc_hcl)} x "
        f"({n(vol_hcl_cm3)} / 1000) = {n(mol_hcl)} mol.",
        "Now divide each by its coefficient in the equation. The smaller "
        "result is the reactant that runs out first.",
        f"Zn: {n(mol_zn)} / 1 = {n(share_zn)}. "
        f"HCl: {n(mol_hcl)} / 2 = {n(share_hcl)}.",
        f"{n(share_hcl)} is the smaller, so the {limiting} is the limiting "
        "reactant and some zinc will be left undissolved.",
        "Part (b). The limiting reactant decides how much product forms. From "
        "the equation 2 moles of HCl give 1 mole of H2.",
        f"Moles of H2 = {n(mol_hcl)} / 2 = {n(mol_h2)} mol.",
        f"Volume at s.t.p. = {n(mol_h2)} x {n(MOLAR_VOLUME)} = {n(vol_h2)} dm3.",
    ],
    answer=(
        f"(a) the {limiting}  (b) {n(vol_h2)} dm3 of hydrogen at s.t.p."
    ),
))


# ------------------------------------------------ 7. concentration in mol/dm3
mass_kcl, vol_kcl_cm3 = 7.45, 250.0
mm_kcl = K + CL
mol_kcl = mass_kcl / mm_kcl
vol_kcl_dm3 = vol_kcl_cm3 / 1000
conc_kcl = mol_kcl / vol_kcl_dm3
EXAMPLES.append(doc(
    num=7, slug="concentration-mol-per-dm3", title="Molar concentration of a solution",
    topic=QUANT, subtopic="Solutions and solubility", section="B3",
    question=(
        f"{n(mass_kcl, 2)} g of potassium chloride, KCl, is dissolved in water "
        f"and made up to {n(vol_kcl_cm3)} cm3 of solution. Calculate the "
        f"concentration of the solution in mol/dm3. [Cl = {n(CL)}, K = {n(K)}]"
    ),
    steps=[
        "Concentration in mol/dm3 is the number of moles of solute in one "
        "cubic decimetre of solution, so find the moles and the volume in dm3.",
        f"Molar mass of KCl = {n(K)} + {n(CL)} = {n(mm_kcl)} g/mol.",
        f"Moles of KCl = {n(mass_kcl, 2)} / {n(mm_kcl)} = {n(mol_kcl)} mol.",
        f"Volume in dm3 = {n(vol_kcl_cm3)} / 1000 = {n(vol_kcl_dm3)} dm3, "
        "since 1 dm3 = 1000 cm3.",
        f"Concentration = {n(mol_kcl)} / {n(vol_kcl_dm3)} = {n(conc_kcl)} "
        "mol/dm3.",
        "Note that the volume is the volume of the solution, not the volume of "
        "water added. The solid is dissolved in a little water and then made up "
        "to the mark.",
    ],
    answer=f"{n(conc_kcl)} mol/dm3",
))


# -------------------------------------------------- 8. concentration in g/dm3
conc_h2so4 = 0.5
mm_h2so4 = 2 * H + S + 4 * O
mass_conc_h2so4 = conc_h2so4 * mm_h2so4
mass_conc_naoh = 8.0
mm_naoh_8 = NA + O + H
molar_conc_naoh = mass_conc_naoh / mm_naoh_8
EXAMPLES.append(doc(
    num=8, slug="concentration-g-per-dm3", title="Converting between mass and molar concentration",
    topic=QUANT, subtopic="Solutions and solubility", section="B3",
    question=(
        f"(a) A solution of tetraoxosulphate(VI) acid, H2SO4, has a "
        f"concentration of {n(conc_h2so4)} mol/dm3. Express this in g/dm3. "
        f"(b) A solution of sodium hydroxide, NaOH, contains "
        f"{n(mass_conc_naoh)} g/dm3. Express this in mol/dm3. "
        f"[H = {n(H)}, O = {n(O)}, Na = {n(NA)}, S = {n(S)}]"
    ),
    steps=[
        "The two units are linked by the molar mass: concentration in g/dm3 = "
        "concentration in mol/dm3 x molar mass.",
        f"Part (a). Molar mass of H2SO4 = (2 x {n(H)}) + {n(S)} + "
        f"(4 x {n(O)}) = {n(2 * H)} + {n(S)} + {n(4 * O)} = {n(mm_h2so4)} "
        "g/mol.",
        f"Concentration = {n(conc_h2so4)} x {n(mm_h2so4)} = "
        f"{n(mass_conc_h2so4)} g/dm3.",
        "Part (b). Going the other way, divide by the molar mass.",
        f"Molar mass of NaOH = {n(NA)} + {n(O)} + {n(H)} = {n(mm_naoh_8)} "
        "g/mol.",
        f"Concentration = {n(mass_conc_naoh)} / {n(mm_naoh_8)} = "
        f"{n(molar_conc_naoh)} mol/dm3.",
    ],
    answer=f"(a) {n(mass_conc_h2so4)} g/dm3  (b) {n(molar_conc_naoh)} mol/dm3",
))


# --------------------------------------------------------------- 9. dilution
c1_dil, v1_dil, v2_dil = 0.8, 50.0, 200.0
c2_dil = c1_dil * v1_dil / v2_dil
dil_factor = v2_dil / v1_dil
EXAMPLES.append(doc(
    num=9, slug="dilution", title="Concentration of a diluted solution",
    topic=QUANT, subtopic="Solutions and solubility", section="B3",
    question=(
        f"{n(v1_dil)} cm3 of {n(c1_dil)} mol/dm3 hydrochloric acid is diluted "
        f"with distilled water to {n(v2_dil)} cm3. Calculate the concentration "
        "of the diluted solution."
    ),
    steps=[
        "Adding water adds no solute, so the number of moles of HCl is the "
        "same before and after. That gives C1V1 = C2V2.",
        f"Check with the moles. Before: {n(c1_dil)} x ({n(v1_dil)} / 1000) = "
        f"{n(c1_dil * v1_dil / 1000, 3)} mol.",
        "Rearranging: C2 = C1V1 / V2. Both volumes are in cm3, so they may be "
        "used as they stand provided they are in the same unit.",
        f"C2 = ({n(c1_dil)} x {n(v1_dil)}) / {n(v2_dil)} = "
        f"{n(c1_dil * v1_dil)} / {n(v2_dil)}.",
        f"C2 = {n(c2_dil)} mol/dm3.",
        f"The volume was multiplied by {n(dil_factor)}, so the concentration "
        f"has fallen by the same factor: {n(c1_dil)} / {n(dil_factor)} = "
        f"{n(c2_dil)}.",
    ],
    answer=f"{n(c2_dil)} mol/dm3",
))


# ------------------------------------------------------------- 10. titration
conc_na2co3, vol_na2co3, vol_hcl_t = 0.100, 25.0, 20.0
mol_na2co3 = conc_na2co3 * vol_na2co3 / 1000
mol_hcl_t = 2 * mol_na2co3      # Na2CO3 + 2HCl, ratio 1 : 2
conc_hcl_t = mol_hcl_t / (vol_hcl_t / 1000)
mm_hcl = H + CL
gdm3_hcl = conc_hcl_t * mm_hcl
EXAMPLES.append(doc(
    num=10, slug="titration", title="Concentration of an acid from titration data",
    topic=QUANT, subtopic="Volumetric analysis", section="B4",
    question=(
        f"{n(vol_na2co3, 1)} cm3 of {n(conc_na2co3, 3)} mol/dm3 sodium "
        "trioxocarbonate(IV) solution, Na2CO3, required "
        f"{n(vol_hcl_t, 1)} cm3 of hydrochloric acid for complete "
        "neutralisation, using methyl orange as indicator. The equation is\n\n"
        "Na2CO3 + 2HCl -> 2NaCl + H2O + CO2\n\n"
        "Calculate the concentration of the acid in (a) mol/dm3, (b) g/dm3. "
        f"[H = {n(H)}, Cl = {n(CL)}]"
    ),
    steps=[
        "Start from the solution whose concentration is known.",
        f"Moles of Na2CO3 = concentration x volume in dm3 = {n(conc_na2co3, 3)} "
        f"x ({n(vol_na2co3, 1)} / 1000) = {n(mol_na2co3, 5)} mol.",
        "The equation gives the mole ratio: 1 mole of Na2CO3 reacts with "
        "2 moles of HCl. This is the step most often skipped.",
        f"Moles of HCl = 2 x {n(mol_na2co3, 5)} = {n(mol_hcl_t, 5)} mol.",
        f"That amount of acid was in {n(vol_hcl_t, 1)} cm3, which is "
        f"{n(vol_hcl_t, 1)} / 1000 = {n(vol_hcl_t / 1000, 4)} dm3.",
        f"Part (a). Concentration = {n(mol_hcl_t, 5)} / {n(vol_hcl_t / 1000, 4)} "
        f"= {n(conc_hcl_t)} mol/dm3.",
        f"Part (b). Molar mass of HCl = {n(H)} + {n(CL)} = {n(mm_hcl)} g/mol.",
        f"Concentration in g/dm3 = {n(conc_hcl_t)} x {n(mm_hcl)} = "
        f"{n(gdm3_hcl, 3)} g/dm3.",
        "Methyl orange is the right indicator here because the salt formed, "
        "NaCl, leaves the solution at the end point acidic rather than neutral.",
    ],
    answer=f"(a) {n(conc_hcl_t)} mol/dm3  (b) {n(gdm3_hcl, 3)} g/dm3",
))


# ------------------------------------------------------ 11. percentage purity
mass_sample, vol_co2_purity = 6.25, 1.12
mol_co2_purity = vol_co2_purity / MOLAR_VOLUME
mm_caco3 = CA + C + 3 * O
mass_pure_caco3 = mol_co2_purity * mm_caco3
purity = mass_pure_caco3 / mass_sample * 100
EXAMPLES.append(doc(
    num=11, slug="percentage-purity", title="Percentage purity of a sample",
    topic=QUANT, subtopic=MOLE, section="B1",
    question=(
        f"{n(mass_sample, 2)} g of impure calcium trioxocarbonate(IV) is heated "
        f"strongly until no more gas is given off. {n(vol_co2_purity, 2)} dm3 "
        "of carbon(IV) oxide, measured at s.t.p., is collected. The equation "
        "is\n\n"
        "CaCO3 -> CaO + CO2\n\n"
        "Assuming the impurities do not decompose, calculate the percentage "
        f"purity of the sample. [C = {n(C)}, O = {n(O)}, Ca = {n(CA)}; molar "
        f"volume of a gas at s.t.p. = {n(MOLAR_VOLUME)} dm3/mol]"
    ),
    steps=[
        "The gas came only from the CaCO3, so work back from it to the mass of "
        "pure CaCO3 in the sample.",
        f"Moles of CO2 = {n(vol_co2_purity, 2)} / {n(MOLAR_VOLUME)} = "
        f"{n(mol_co2_purity)} mol.",
        "From the equation, 1 mole of CaCO3 gives 1 mole of CO2, so the moles "
        "of CaCO3 that decomposed are the same.",
        f"Moles of CaCO3 = {n(mol_co2_purity)} mol.",
        f"Molar mass of CaCO3 = {n(CA)} + {n(C)} + (3 x {n(O)}) = "
        f"{n(mm_caco3)} g/mol.",
        f"Mass of pure CaCO3 = {n(mol_co2_purity)} x {n(mm_caco3)} = "
        f"{n(mass_pure_caco3)} g.",
        "Percentage purity = (mass of pure substance / mass of sample) x 100.",
        f"Purity = ({n(mass_pure_caco3)} / {n(mass_sample, 2)}) x 100 = "
        f"{n(purity)} per cent.",
        f"So {n(mass_sample - mass_pure_caco3)} g of the sample was impurity.",
    ],
    answer=f"{n(purity)} per cent pure",
))


# ------------------------------------------------------- 12. percentage yield
mass_caco3_y, actual_cao = 50.0, 21.0
mol_caco3_y = mass_caco3_y / mm_caco3
mm_cao = CA + O
theoretical_cao = mol_caco3_y * mm_cao
yield_pc = actual_cao / theoretical_cao * 100
EXAMPLES.append(doc(
    num=12, slug="percentage-yield", title="Percentage yield of a reaction",
    topic=QUANT, subtopic=MOLE, section="B1",
    question=(
        f"{n(mass_caco3_y)} g of pure calcium trioxocarbonate(IV) is heated and "
        f"{n(actual_cao)} g of calcium oxide is obtained. The equation is\n\n"
        "CaCO3 -> CaO + CO2\n\n"
        "Calculate (a) the theoretical yield of calcium oxide, (b) the "
        f"percentage yield. [C = {n(C)}, O = {n(O)}, Ca = {n(CA)}]"
    ),
    steps=[
        "Part (a). The theoretical yield is what the equation says should be "
        "obtained if the reaction went to completion with no losses.",
        f"Molar mass of CaCO3 = {n(CA)} + {n(C)} + (3 x {n(O)}) = "
        f"{n(mm_caco3)} g/mol.",
        f"Moles of CaCO3 = {n(mass_caco3_y)} / {n(mm_caco3)} = "
        f"{n(mol_caco3_y)} mol.",
        "From the equation, 1 mole of CaCO3 gives 1 mole of CaO, so "
        f"{n(mol_caco3_y)} mol of CaO should form.",
        f"Molar mass of CaO = {n(CA)} + {n(O)} = {n(mm_cao)} g/mol, so the "
        f"theoretical yield = {n(mol_caco3_y)} x {n(mm_cao)} = "
        f"{n(theoretical_cao)} g.",
        "Part (b). Percentage yield = (actual yield / theoretical yield) x 100.",
        f"Percentage yield = ({n(actual_cao)} / {n(theoretical_cao)}) x 100 = "
        f"{n(yield_pc)} per cent.",
        "It is below 100 per cent because the decomposition may be incomplete "
        "and because solid is lost in transferring it from the crucible.",
    ],
    answer=(
        f"(a) {n(theoretical_cao)} g  (b) {n(yield_pc)} per cent"
    ),
))


# ------------------------------------------------------- 13. oxidation number
# K2Cr2O7: 2(+1) + 2x + 7(-2) = 0
ox_cr = (0 - 2 * (+1) - 7 * (-2)) / 2
# NH4+: x + 4(+1) = +1
ox_n = (+1) - 4 * (+1)
EXAMPLES.append(doc(
    num=13, slug="oxidation-number", title="Oxidation number of an element in a compound",
    topic=REACTIONS, subtopic="Oxidation and reduction", section="C2",
    question=(
        "Determine the oxidation number of (a) chromium in potassium "
        "heptaoxodichromate(VI), K2Cr2O7, (b) nitrogen in the ammonium ion, "
        "NH4+."
    ),
    steps=[
        "Use the standard rules: potassium, a Group I metal, is +1; oxygen is "
        "-2; hydrogen in a compound is +1; the oxidation numbers in a neutral "
        "compound add to zero, and in a polyatomic ion they add to the charge "
        "on the ion.",
        "Part (a). Let the oxidation number of chromium be x. K2Cr2O7 is "
        "neutral, and there are two chromium atoms and seven oxygen atoms.",
        "2(+1) + 2x + 7(-2) = 0.",
        f"{n(2 * 1)} + 2x - {n(7 * 2)} = 0, so 2x = {n(7 * 2 - 2 * 1)}.",
        f"x = +{n(ox_cr)}.",
        "Part (b). Let the oxidation number of nitrogen be y. NH4+ carries a "
        "charge of +1, so the oxidation numbers add to +1.",
        "y + 4(+1) = +1.",
        f"y = +1 - {n(4 * 1)} = {n(ox_n)}.",
        "An oxidation number is not the same thing as a charge on an atom. It "
        "is a bookkeeping device, and it can be negative, positive or "
        "fractional.",
    ],
    answer=f"(a) +{n(ox_cr)}  (b) {n(ox_n)}",
))


# ------------------------------------------------------- 14. redox half-equation
# Cr2O7 2- reduced to Cr3+ in acid solution.
cr_atoms = 2
o_atoms = 7
water_needed = o_atoms                 # one O per H2O
h_ions_needed = 2 * water_needed       # two H per H2O
charge_left_no_e = -2 + h_ions_needed
charge_right = cr_atoms * (+3)
electrons_needed = charge_left_no_e - charge_right
half_equation = (
    f"Cr2O7 2- + {int(h_ions_needed)}H+ + {int(electrons_needed)}e- -> "
    f"{int(cr_atoms)}Cr3+ + {int(water_needed)}H2O"
)
EXAMPLES.append(doc(
    num=14, slug="redox-half-equation", title="Balancing a redox half-equation",
    topic=REACTIONS, subtopic="Oxidation and reduction", section="C2",
    question=(
        "In acid solution the heptaoxodichromate(VI) ion, Cr2O7 2-, is reduced "
        "to the chromium(III) ion, Cr3+. Write the balanced half-equation for "
        "this reduction."
    ),
    steps=[
        "Work through the standard order: balance the atoms other than oxygen "
        "and hydrogen, then add water for the oxygen, then hydrogen ions for "
        "the hydrogen, then electrons to balance the charge.",
        f"Chromium first. There are {int(cr_atoms)} chromium atoms on the left, "
        f"so write {int(cr_atoms)}Cr3+ on the right.",
        "Cr2O7 2- -> 2Cr3+",
        f"Oxygen next. There are {int(o_atoms)} oxygen atoms on the left, so "
        f"add {int(water_needed)}H2O on the right.",
        f"Cr2O7 2- -> 2Cr3+ + {int(water_needed)}H2O",
        f"Hydrogen next. {int(water_needed)}H2O contains "
        f"{int(h_ions_needed)} hydrogen atoms, so add {int(h_ions_needed)}H+ "
        "on the left. The solution is acidic, so hydrogen ions are available.",
        f"Cr2O7 2- + {int(h_ions_needed)}H+ -> 2Cr3+ + {int(water_needed)}H2O",
        f"Now the charge. Left: (-2) + (+{int(h_ions_needed)}) = "
        f"+{int(charge_left_no_e)}. Right: {int(cr_atoms)} x (+3) = "
        f"+{int(charge_right)}.",
        f"The left is more positive by {int(electrons_needed)}, so add "
        f"{int(electrons_needed)}e- to the left.",
        half_equation,
        f"Check it against the oxidation numbers. In Cr2O7 2-, "
        f"2x + 7(-2) = -2 gives x = +{n(ox_cr)}. Each chromium falls from "
        f"+{n(ox_cr)} to +3, a gain of {n(ox_cr - 3)} electrons, and there are "
        f"{int(cr_atoms)} of them, so {int(electrons_needed)} electrons in "
        "all. The two methods agree.",
    ],
    answer=half_equation,
))


# ------------------------------------------------------------ 15. electrolysis
current, minutes, seconds = 5.0, 32.0, 10.0
time_s = minutes * 60 + seconds
charge_q = current * time_s
mol_electrons = charge_q / FARADAY
electrons_per_cu = 2
mol_cu = mol_electrons / electrons_per_cu
mass_cu = mol_cu * CU
EXAMPLES.append(doc(
    num=15, slug="electrolysis-faraday", title="Mass deposited during electrolysis",
    topic=REACTIONS, subtopic="Electrolysis", section="C3",
    question=(
        f"A current of {n(current)} A is passed for {n(minutes)} minutes "
        f"{n(seconds)} seconds through aqueous copper(II) "
        "tetraoxosulphate(VI) using inert electrodes. Calculate the mass of "
        "copper deposited at the cathode. The cathode reaction is\n\n"
        "Cu2+ + 2e- -> Cu\n\n"
        f"[Cu = {n(CU)}; 1 faraday = {n(FARADAY)} C/mol]"
    ),
    steps=[
        "First find the quantity of electricity, Q = It, with the time in "
        "seconds.",
        f"Time = ({n(minutes)} x 60) + {n(seconds)} = {n(time_s)} s.",
        f"Q = {n(current)} x {n(time_s)} = {n(charge_q)} C.",
        f"One faraday, {n(FARADAY)} C, is the charge on one mole of electrons, "
        "so divide by it to get the moles of electrons passed.",
        f"Moles of electrons = {n(charge_q)} / {n(FARADAY)} = "
        f"{n(mol_electrons)} mol.",
        f"The cathode equation shows that {electrons_per_cu} moles of electrons "
        "deposit 1 mole of copper, because Cu2+ is doubly charged.",
        f"Moles of Cu = {n(mol_electrons)} / {electrons_per_cu} = "
        f"{n(mol_cu)} mol.",
        f"Mass of Cu = {n(mol_cu)} x {n(CU)} = {n(mass_cu)} g.",
        "Copper is deposited rather than hydrogen because Cu2+ is below H+ in "
        "the discharge series and so is discharged in preference to it.",
    ],
    answer=f"{n(mass_cu)} g of copper",
))


# --------------------------------------------------------- 16. heat of reaction
vol_acid, vol_alkali, conc_neut = 100.0, 100.0, 1.0
temp_rise = 6.8
mass_solution_g = vol_acid + vol_alkali      # density taken as 1 g/cm3
mass_solution_kg = mass_solution_g / 1000
heat_q = mass_solution_kg * C_WATER * temp_rise
mol_water_formed = conc_neut * vol_acid / 1000   # HCl + NaOH -> NaCl + H2O, 1 : 1
heat_per_mole_kj = -heat_q / mol_water_formed / 1000
EXAMPLES.append(doc(
    num=16, slug="heat-of-reaction", title="Heat of neutralisation from a temperature rise",
    topic=REACTIONS, subtopic="Energy changes", section="C4",
    question=(
        f"{n(vol_acid)} cm3 of {n(conc_neut)} mol/dm3 hydrochloric acid is "
        f"mixed with {n(vol_alkali)} cm3 of {n(conc_neut)} mol/dm3 sodium "
        f"hydroxide solution in a plastic cup. The temperature rises by "
        f"{n(temp_rise)} degrees Celsius. The equation is\n\n"
        "HCl + NaOH -> NaCl + H2O\n\n"
        "Calculate (a) the heat given out, (b) the heat of neutralisation in "
        "kJ/mol. [Take the density of the mixture as 1 g/cm3 and the specific "
        f"heat capacity of water as {n(C_WATER)} J/kg/K, that is "
        f"{n(C_WATER / 1000)} J/g/K]"
    ),
    steps=[
        "Part (a). The heat is taken up by the mixture, so use Q = mc x change "
        "in temperature, with m the mass of the mixture.",
        f"Mass = {n(vol_acid)} + {n(vol_alkali)} = {n(mass_solution_g)} cm3, "
        f"and at 1 g/cm3 that is {n(mass_solution_g)} g, or "
        f"{n(mass_solution_kg, 3)} kg.",
        f"Q = {n(mass_solution_kg, 3)} x {n(C_WATER)} x {n(temp_rise)}.",
        f"Q = {n(heat_q)} J.",
        "Part (b). Find how many moles of water were formed, then divide.",
        f"Moles of HCl = {n(conc_neut)} x ({n(vol_acid)} / 1000) = "
        f"{n(mol_water_formed)} mol, and the same for NaOH. The ratio in the "
        f"equation is 1 to 1, so {n(mol_water_formed)} mol of water is formed "
        "and neither reactant is in excess.",
        f"Heat per mole = {n(heat_q)} / {n(mol_water_formed)} = "
        f"{n(heat_q / mol_water_formed)} J/mol, which is "
        f"{n(heat_q / mol_water_formed / 1000)} kJ/mol.",
        "The temperature rose, so the reaction is exothermic and the heat of "
        f"neutralisation is written with a negative sign: "
        f"{n(heat_per_mole_kj)} kJ/mol.",
        "This is close to the accepted value for a strong acid with a strong "
        "alkali, because in every such pair the reaction is really the same "
        "one, H+ + OH- -> H2O.",
    ],
    answer=(
        f"(a) {n(heat_q)} J  (b) {n(heat_per_mole_kj)} kJ/mol"
    ),
))


# ------------------------------------------------------------------ 17. rate
conc_start, conc_end, time_rate = 0.50, 0.20, 60.0
rate = (conc_start - conc_end) / time_rate
EXAMPLES.append(doc(
    num=17, slug="rate-of-reaction", title="Average rate from a change in concentration",
    topic=REACTIONS, subtopic="Rates of reaction", section="C5",
    question=(
        "In a reaction the concentration of one of the reactants falls from "
        f"{n(conc_start, 2)} mol/dm3 to {n(conc_end, 2)} mol/dm3 in "
        f"{n(time_rate)} seconds. Calculate the average rate of the reaction "
        "over that interval, and state its unit."
    ),
    steps=[
        "The average rate is the change in the amount of a reactant or product "
        "divided by the time taken.",
        f"Change in concentration = {n(conc_start, 2)} - {n(conc_end, 2)} = "
        f"{n(conc_start - conc_end, 2)} mol/dm3.",
        f"Average rate = {n(conc_start - conc_end, 2)} / {n(time_rate)}.",
        f"Average rate = {n(rate, 4)} mol/dm3 per second.",
        "The rate is quoted as a positive number even though the concentration "
        "fell, because rate means how fast the change happens.",
        "This is an average over the whole interval. The actual rate was "
        "highest at the start, when the reactant was most concentrated, and "
        "fell as it was used up.",
    ],
    answer=f"{n(rate, 4)} mol/dm3 per second",
))


# ----------------------------------------------------------- 18. equilibrium
so2_eq, o2_eq, so3_eq = 0.20, 0.10, 0.40
kc = (so3_eq ** 2) / ((so2_eq ** 2) * o2_eq)
EXAMPLES.append(doc(
    num=18, slug="equilibrium-constant", title="Equilibrium constant expression and value",
    topic=REACTIONS, subtopic="Chemical equilibrium", section="C6",
    question=(
        "Sulphur(IV) oxide and oxygen reach equilibrium in a closed vessel "
        "of volume 1 dm3 according to\n\n"
        "2SO2(g) + O2(g) reversible 2SO3(g)\n\n"
        f"At equilibrium the vessel contains {n(so2_eq, 2)} mol/dm3 of SO2, "
        f"{n(o2_eq, 2)} mol/dm3 of O2 and {n(so3_eq, 2)} mol/dm3 of SO3. "
        "Write the expression for Kc and calculate its value, with its unit."
    ),
    steps=[
        "Products go on top, reactants underneath, each concentration raised "
        "to the power of its coefficient in the balanced equation.",
        "Kc = [SO3]^2 / ([SO2]^2 x [O2])",
        f"Substitute the equilibrium concentrations: Kc = ({n(so3_eq, 2)})^2 / "
        f"(({n(so2_eq, 2)})^2 x {n(o2_eq, 2)}).",
        f"The top is {n(so3_eq ** 2, 4)} and the bottom is "
        f"{n(so2_eq ** 2, 4)} x {n(o2_eq, 2)} = "
        f"{n(so2_eq ** 2 * o2_eq, 4)}.",
        f"Kc = {n(so3_eq ** 2, 4)} / {n(so2_eq ** 2 * o2_eq, 4)} = {n(kc)}.",
        "For the unit, put mol/dm3 into the expression: (mol/dm3)^2 divided by "
        "(mol/dm3)^2 x (mol/dm3) leaves 1 / (mol/dm3), which is dm3/mol.",
        f"Kc = {n(kc)} dm3/mol. It is large, so at this temperature the "
        "equilibrium lies well over towards the sulphur(VI) oxide.",
        "Kc is changed only by temperature. Adding a catalyst, such as the "
        "vanadium(V) oxide used in the Contact process, brings equilibrium on "
        "sooner but leaves Kc alone.",
    ],
    answer=f"Kc = [SO3]^2 / ([SO2]^2 x [O2]), and its value is {n(kc)} dm3/mol",
))


# ------------------------------------------------- 19. relative molecular mass
rmm_caoh2 = CA + 2 * (O + H)
rmm_cuso4_5h2o = CU + S + 4 * O + 5 * (2 * H + O)
EXAMPLES.append(doc(
    num=19, slug="relative-molecular-mass", title="Relative molecular mass from a formula",
    topic=QUANT, subtopic=MOLE, section="B1",
    question=(
        "Calculate the relative molecular mass of (a) calcium hydroxide, "
        "Ca(OH)2, (b) hydrated copper(II) tetraoxosulphate(VI), CuSO4.5H2O. "
        f"[H = {n(H)}, O = {n(O)}, S = {n(S)}, Ca = {n(CA)}, Cu = {n(CU)}]"
    ),
    steps=[
        "The relative molecular mass is the sum of the relative atomic masses "
        "of all the atoms shown in the formula. A bracket multiplies "
        "everything inside it.",
        f"Part (a). Ca(OH)2 has one Ca and two OH groups, so it is {n(CA)} + "
        f"2 x ({n(O)} + {n(H)}).",
        f"= {n(CA)} + (2 x {n(O + H)}) = {n(CA)} + {n(2 * (O + H))} = "
        f"{n(rmm_caoh2)}.",
        "Part (b). The dot in CuSO4.5H2O means five water molecules are part "
        "of the crystal, so they count towards the mass.",
        f"CuSO4 = {n(CU)} + {n(S)} + (4 x {n(O)}) = {n(CU + S + 4 * O)}.",
        f"5H2O = 5 x ((2 x {n(H)}) + {n(O)}) = 5 x {n(2 * H + O)} = "
        f"{n(5 * (2 * H + O))}.",
        f"Total = {n(CU + S + 4 * O)} + {n(5 * (2 * H + O))} = "
        f"{n(rmm_cuso4_5h2o)}.",
        "Relative molecular mass has no unit, being a ratio of masses. The "
        "same number in grams per mole is the molar mass.",
    ],
    answer=f"(a) {n(rmm_caoh2)}  (b) {n(rmm_cuso4_5h2o)}",
))


# ------------------------------------------------------- 20. general gas law
v1_gas, t1_celsius, p1_gas = 380.0, 27.0, 800.0
t1_gas = t1_celsius + 273
t2_gas, p2_gas = 273.0, 760.0
v2_gas = p1_gas * v1_gas * t2_gas / (t1_gas * p2_gas)
EXAMPLES.append(doc(
    num=20, slug="general-gas-law", title="Correcting a gas volume to s.t.p.",
    topic=QUANT, subtopic="Gas laws", section="B2",
    question=(
        f"{n(v1_gas)} cm3 of a gas is collected at {n(t1_celsius)} degrees "
        f"Celsius and {n(p1_gas)} mmHg. Calculate its volume at s.t.p., which "
        f"is {n(t2_gas)} K and {n(p2_gas)} mmHg."
    ),
    steps=[
        "For a fixed mass of gas the general gas equation applies: "
        "P1V1 / T1 = P2V2 / T2. The temperatures must be in kelvin.",
        f"T1 = {n(t1_celsius)} + 273 = {n(t1_gas)} K. T2 = {n(t2_gas)} K.",
        "Both pressures are already in mmHg, so they may be used as they are.",
        "Rearranging for V2: V2 = P1V1T2 / (T1P2).",
        f"V2 = ({n(p1_gas)} x {n(v1_gas)} x {n(t2_gas)}) / ({n(t1_gas)} x "
        f"{n(p2_gas)}).",
        f"Taking the pressure factor first: {n(p1_gas)} / {n(p2_gas)} = "
        f"{n(p1_gas / p2_gas, 4)}, and the temperature factor: {n(t2_gas)} / "
        f"{n(t1_gas)} = {n(t2_gas / t1_gas, 4)}.",
        f"V2 = {n(v1_gas)} x {n(p1_gas / p2_gas, 4)} x "
        f"{n(t2_gas / t1_gas, 4)} = {n(v2_gas)} cm3.",
        "The two changes pull opposite ways. The pressure falls from "
        f"{n(p1_gas)} to {n(p2_gas)} mmHg, which on its own would expand the "
        f"gas by a factor of {n(p1_gas / p2_gas, 4)}; the temperature falls "
        f"from {n(t1_gas)} K to {n(t2_gas)} K, which on its own would shrink "
        f"it by a factor of {n(t2_gas / t1_gas, 4)}. The cooling is the larger "
        f"effect, so the corrected volume is smaller than {n(v1_gas)} cm3.",
    ],
    answer=f"{n(v2_gas)} cm3",
))


# ------------------------------------------------- 21. homologous series formula
rmm_alkane = 58.0
n_alkane = (rmm_alkane - 2) / 14
alkane_formula = f"C{round(n_alkane)}H{round(2 * n_alkane + 2)}"
alkane_names = {1: "methane", 2: "ethane", 3: "propane", 4: "butane", 5: "pentane"}
alkane_name = alkane_names[round(n_alkane)]

rmm_alkyne = 40.0
n_alkyne = (rmm_alkyne + 2) / 14
alkyne_formula = f"C{round(n_alkyne)}H{round(2 * n_alkyne - 2)}"
alkyne_names = {2: "ethyne", 3: "propyne", 4: "butyne"}
alkyne_name = alkyne_names[round(n_alkyne)]

EXAMPLES.append(doc(
    num=21, slug="homologous-series-formula",
    title="Molecular formula of a member of a homologous series",
    topic="Organic chemistry", subtopic="Hydrocarbons", section="E1",
    question=(
        f"(a) An alkane has a relative molecular mass of {n(rmm_alkane)}. "
        f"(b) An alkyne has a relative molecular mass of {n(rmm_alkyne)}. "
        "Determine the molecular formula and the name of each. "
        f"[H = {n(H)}, C = {n(C)}]"
    ),
    steps=[
        "Start from the general formula of the series and write its relative "
        "molecular mass in terms of n.",
        f"Part (a). Alkanes are CnH2n+2, so the mass is "
        f"({n(C)}n) + ({n(H)} x (2n + 2)) = 12n + 2n + 2 = 14n + 2.",
        f"14n + 2 = {n(rmm_alkane)}, so 14n = {n(rmm_alkane - 2)} and "
        f"n = {n(n_alkane)}.",
        f"With n = {n(n_alkane)} the formula is {alkane_formula}, which is "
        f"{alkane_name}.",
        f"Part (b). Alkynes are CnH2n-2, so the mass is 12n + 2n - 2 = "
        "14n - 2.",
        f"14n - 2 = {n(rmm_alkyne)}, so 14n = {n(rmm_alkyne + 2)} and "
        f"n = {n(n_alkyne)}.",
        f"With n = {n(n_alkyne)} the formula is {alkyne_formula}, which is "
        f"{alkyne_name}.",
        f"Check both. {alkane_formula}: "
        f"({n(round(n_alkane))} x {n(C)}) + ({n(round(2 * n_alkane + 2))} x "
        f"{n(H)}) = {n(round(n_alkane) * C + round(2 * n_alkane + 2) * H)}. "
        f"{alkyne_formula}: ({n(round(n_alkyne))} x {n(C)}) + "
        f"({n(round(2 * n_alkyne - 2))} x {n(H)}) = "
        f"{n(round(n_alkyne) * C + round(2 * n_alkyne - 2) * H)}.",
        "Members of one homologous series differ by CH2, which is 14 units of "
        "mass. That is why 14 keeps appearing.",
    ],
    answer=(
        f"(a) {alkane_formula}, {alkane_name}  "
        f"(b) {alkyne_formula}, {alkyne_name}"
    ),
))


# ------------------------------------------- 22. alkanol and alkanoic acid RMM
ORGANIC = "Organic chemistry"
OXYGENATED = "Alkanols, alkanoic acids and alkanoates"
ENVIRONMENT = "Chemistry of the environment"

ch2_unit = C + 2 * H                     # 14, the difference between members
alkanol_tail = 2 * H + O                 # the extra H2 and O over CnH2n
rmm_alkanol = 46.0
n_alkanol = (rmm_alkanol - alkanol_tail) / ch2_unit
alkanol_formula = f"C{round(n_alkanol)}H{round(2 * n_alkanol + 1)}OH"
alkanol_names = {1: "methanol", 2: "ethanol", 3: "propanol", 4: "butanol"}
alkanol_name = alkanol_names[round(n_alkanol)]

acid_tail = 2 * O                        # CnH2nO2, so the tail is two oxygens
rmm_acid = 60.0
n_acid = (rmm_acid - acid_tail) / ch2_unit
acid_formula = f"C{round(n_acid)}H{round(2 * n_acid)}O2"
acid_condensed = {1: "HCOOH", 2: "CH3COOH", 3: "C2H5COOH"}
acid_names = {1: "methanoic acid", 2: "ethanoic acid", 3: "propanoic acid"}
acid_short, acid_name = acid_condensed[round(n_acid)], acid_names[round(n_acid)]

EXAMPLES.append(doc(
    num=22, slug="alkanol-formula",
    title="Molecular formula of an alkanol and of an alkanoic acid",
    topic=ORGANIC, subtopic=OXYGENATED, section="E2",
    question=(
        f"(a) An alkanol has a relative molecular mass of {n(rmm_alkanol)}. "
        f"(b) An alkanoic acid has a relative molecular mass of {n(rmm_acid)}. "
        "Determine the molecular formula and the name of each. "
        f"[H = {n(H)}, C = {n(C)}, O = {n(O)}]"
    ),
    steps=[
        "As with the hydrocarbons, start from the general formula of the series "
        "and write its relative molecular mass in terms of n.",
        f"Part (a). An alkanol is CnH2n+1OH, which is the same as CnH2n+2O, so "
        f"its mass is ({n(C)}n) + (2n + 2) + {n(O)} = 12n + 2n + 2 + 16 = "
        f"14n + {n(alkanol_tail)}.",
        f"14n + {n(alkanol_tail)} = {n(rmm_alkanol)}, so "
        f"14n = {n(rmm_alkanol - alkanol_tail)} and n = {n(n_alkanol)}.",
        f"With n = {n(n_alkanol)} the formula is {alkanol_formula}, which is "
        f"{alkanol_name}.",
        f"Part (b). An alkanoic acid is CnH2n+1COOH, which is the same as "
        f"CnH2nO2, so its mass is 12n + 2n + (2 x {n(O)}) = 14n + "
        f"{n(acid_tail)}. The carbon of the -COOH group is counted in n.",
        f"14n + {n(acid_tail)} = {n(rmm_acid)}, so "
        f"14n = {n(rmm_acid - acid_tail)} and n = {n(n_acid)}.",
        f"With n = {n(n_acid)} the formula is {acid_formula}, written out as "
        f"{acid_short}, which is {acid_name}.",
        f"Check both. {alkanol_formula}: ({n(round(n_alkanol))} x {n(C)}) + "
        f"({n(round(2 * n_alkanol + 2))} x {n(H)}) + {n(O)} = "
        f"{n(round(n_alkanol) * C + round(2 * n_alkanol + 2) * H + O)}. "
        f"{acid_formula}: ({n(round(n_acid))} x {n(C)}) + "
        f"({n(round(2 * n_acid))} x {n(H)}) + (2 x {n(O)}) = "
        f"{n(round(n_acid) * C + round(2 * n_acid) * H + 2 * O)}.",
        "Note that an alkanol and an alkanoic acid can share a relative "
        f"molecular mass: {n(rmm_alkanol)} fits {alkanol_name} and also fits "
        f"{acid_condensed[1]}, {acid_names[1]}. The mass alone does not settle "
        "which family a compound belongs to; the functional group does.",
    ],
    answer=(
        f"(a) {alkanol_formula}, {alkanol_name}  "
        f"(b) {acid_formula}, that is {acid_short}, {acid_name}"
    ),
))


# ------------------------------------------- 23. percentage composition of an ester
ester_c, ester_h, ester_o = 4, 8, 2          # ethyl ethanoate, CH3COOC2H5
rmm_ester = ester_c * C + ester_h * H + ester_o * O
mass_c_in_ester = ester_c * C
pc_c_ester = mass_c_in_ester / rmm_ester * 100
EXAMPLES.append(doc(
    num=23, slug="ester-percentage-composition",
    title="Percentage by mass of carbon in an ester",
    topic=ORGANIC, subtopic=OXYGENATED, section="E2",
    question=(
        "Ethyl ethanoate, CH3COOC2H5, is the alkanoate formed when ethanol "
        "reacts with ethanoic acid. Calculate (a) its relative molecular mass, "
        "(b) the percentage by mass of carbon in it, to two decimal places. "
        f"[H = {n(H)}, C = {n(C)}, O = {n(O)}]"
    ),
    steps=[
        "Part (a). First count the atoms in the condensed formula. "
        f"CH3COOC2H5 has {ester_c} carbon atoms, {ester_h} hydrogen atoms and "
        f"{ester_o} oxygen atoms, so its molecular formula is "
        f"C{ester_c}H{ester_h}O{ester_o}.",
        f"Relative molecular mass = ({ester_c} x {n(C)}) + ({ester_h} x "
        f"{n(H)}) + ({ester_o} x {n(O)}).",
        f"= {n(ester_c * C)} + {n(ester_h * H)} + {n(ester_o * O)} = "
        f"{n(rmm_ester)}.",
        "Part (b). The percentage by mass of an element is the mass that "
        "element contributes, divided by the relative molecular mass, times "
        "100.",
        f"Mass contributed by carbon = {ester_c} x {n(C)} = "
        f"{n(mass_c_in_ester)}.",
        f"Percentage of carbon = ({n(mass_c_in_ester)} / {n(rmm_ester)}) x 100 "
        f"= {n(pc_c_ester)} per cent.",
        "Check the three percentages add to 100. Carbon "
        f"{n(pc_c_ester)}, hydrogen "
        f"{n(ester_h * H / rmm_ester * 100)}, oxygen "
        f"{n(ester_o * O / rmm_ester * 100)}, and "
        f"{n(pc_c_ester)} + {n(ester_h * H / rmm_ester * 100)} + "
        f"{n(ester_o * O / rmm_ester * 100)} = "
        f"{n(pc_c_ester + ester_h * H / rmm_ester * 100 + ester_o * O / rmm_ester * 100)} "
        "to two decimal places.",
    ],
    answer=f"(a) {n(rmm_ester)}  (b) {n(pc_c_ester)} per cent carbon",
))


# ------------------------------------------------ 24. combustion of ethanol
mass_ethanol = 9.2
mm_ethanol = 2 * C + 6 * H + O                 # C2H5OH
mol_ethanol = mass_ethanol / mm_ethanol
co2_per_ethanol = 2                            # C2H5OH + 3O2 -> 2CO2 + 3H2O
mol_co2_burn = mol_ethanol * co2_per_ethanol
vol_co2_burn = mol_co2_burn * MOLAR_VOLUME
mm_co2_burn = C + 2 * O
mass_co2_burn = mol_co2_burn * mm_co2_burn
EXAMPLES.append(doc(
    num=24, slug="ethanol-combustion",
    title="Carbon(IV) oxide from the complete combustion of ethanol",
    topic=ORGANIC, subtopic=OXYGENATED, section="E2",
    question=(
        f"{n(mass_ethanol)} g of ethanol, C2H5OH, is burnt completely in "
        "oxygen. The equation is\n\n"
        "C2H5OH + 3O2 -> 2CO2 + 3H2O\n\n"
        "Calculate (a) the volume of carbon(IV) oxide produced, measured at "
        "s.t.p., (b) its mass. "
        f"[H = {n(H)}, C = {n(C)}, O = {n(O)}; molar volume of a gas at s.t.p. "
        f"= {n(MOLAR_VOLUME)} dm3/mol]"
    ),
    steps=[
        "The equation is a statement about moles, so turn the mass of ethanol "
        "into moles first.",
        f"Molar mass of C2H5OH = (2 x {n(C)}) + (6 x {n(H)}) + {n(O)} = "
        f"{n(2 * C)} + {n(6 * H)} + {n(O)} = {n(mm_ethanol)} g/mol.",
        f"Moles of ethanol = {n(mass_ethanol)} / {n(mm_ethanol)} = "
        f"{n(mol_ethanol)} mol.",
        f"From the equation, 1 mole of ethanol gives {co2_per_ethanol} moles "
        "of CO2, because both carbon atoms end up as carbon(IV) oxide.",
        f"Moles of CO2 = {co2_per_ethanol} x {n(mol_ethanol)} = "
        f"{n(mol_co2_burn)} mol.",
        f"Part (a). Volume at s.t.p. = moles x {n(MOLAR_VOLUME)} = "
        f"{n(mol_co2_burn)} x {n(MOLAR_VOLUME)} = {n(vol_co2_burn)} dm3.",
        f"Part (b). Molar mass of CO2 = {n(C)} + (2 x {n(O)}) = "
        f"{n(mm_co2_burn)} g/mol.",
        f"Mass = {n(mol_co2_burn)} x {n(mm_co2_burn)} = {n(mass_co2_burn)} g.",
        "Complete combustion is assumed because oxygen is in plenty. In a "
        "limited supply the ethanol would give carbon(II) oxide or soot "
        "instead, and this arithmetic would not apply.",
    ],
    answer=(
        f"(a) {n(vol_co2_burn)} dm3 at s.t.p.  "
        f"(b) {n(mass_co2_burn)} g of carbon(IV) oxide"
    ),
))


# --------------------------------------------------------- 25. hardness of water
mass_ca_hco3 = 0.162           # g per dm3, temporary hardness
mm_ca_hco3 = CA + 2 * (H + C + 3 * O)
mol_ca_hco3 = mass_ca_hco3 / mm_ca_hco3
mass_mgso4 = 0.120             # g per dm3, permanent hardness
mm_mgso4 = MG + S + 4 * O
mol_mgso4 = mass_mgso4 / mm_mgso4
total_hardness_mol = mol_ca_hco3 + mol_mgso4
mm_caco3_h = CA + C + 3 * O
ppm_total = total_hardness_mol * mm_caco3_h * 1000     # mg per dm3
ppm_after_boiling = mol_mgso4 * mm_caco3_h * 1000
EXAMPLES.append(doc(
    num=25, slug="water-hardness",
    title="Total hardness of a water sample in mol per dm3 and in ppm",
    topic=ENVIRONMENT, subtopic="Hard water", section="F1",
    question=(
        "One cubic decimetre of a sample of hard water contains "
        f"{n(mass_ca_hco3, 3)} g of calcium hydrogentrioxocarbonate(IV), "
        f"Ca(HCO3)2, and {n(mass_mgso4, 3)} g of magnesium "
        "tetraoxosulphate(VI), MgSO4. Calculate (a) the total hardness in "
        "mol/dm3 of calcium and magnesium ions, (b) the total hardness in parts "
        "per million expressed as CaCO3, (c) the hardness remaining after the "
        "water has been boiled, in ppm. "
        f"[H = {n(H)}, C = {n(C)}, O = {n(O)}, Mg = {n(MG)}, S = {n(S)}, "
        f"Ca = {n(CA)}. Take 1 dm3 of water to have a mass of 1 kg, so that "
        "1 ppm is 1 mg/dm3.]"
    ),
    steps=[
        "Part (a). Hardness is caused by the calcium and magnesium ions, and "
        "each of these salts gives one such ion per formula unit, so find the "
        "moles of each salt.",
        f"Molar mass of Ca(HCO3)2 = {n(CA)} + 2 x ({n(H)} + {n(C)} + "
        f"(3 x {n(O)})) = {n(CA)} + (2 x {n(H + C + 3 * O)}) = "
        f"{n(mm_ca_hco3)} g/mol.",
        f"Moles of Ca(HCO3)2 = {n(mass_ca_hco3, 3)} / {n(mm_ca_hco3)} = "
        f"{n(mol_ca_hco3, 5)} mol, which is {n(mol_ca_hco3, 5)} mol of Ca2+.",
        f"Molar mass of MgSO4 = {n(MG)} + {n(S)} + (4 x {n(O)}) = "
        f"{n(mm_mgso4)} g/mol.",
        f"Moles of MgSO4 = {n(mass_mgso4, 3)} / {n(mm_mgso4)} = "
        f"{n(mol_mgso4, 5)} mol, which is {n(mol_mgso4, 5)} mol of Mg2+.",
        f"Total hardness = {n(mol_ca_hco3, 5)} + {n(mol_mgso4, 5)} = "
        f"{n(total_hardness_mol, 5)} mol/dm3.",
        "Part (b). Hardness is conventionally quoted as though all of it were "
        "calcium trioxocarbonate(IV), so convert the same number of moles into "
        "a mass of CaCO3.",
        f"Molar mass of CaCO3 = {n(CA)} + {n(C)} + (3 x {n(O)}) = "
        f"{n(mm_caco3_h)} g/mol.",
        f"Mass as CaCO3 = {n(total_hardness_mol, 5)} x {n(mm_caco3_h)} = "
        f"{n(total_hardness_mol * mm_caco3_h, 3)} g/dm3, which is "
        f"{n(ppm_total)} mg/dm3, that is {n(ppm_total)} ppm.",
        "Part (c). Boiling decomposes only the hydrogentrioxocarbonate(IV), "
        "Ca(HCO3)2 -> CaCO3 + H2O + CO2, so the temporary hardness is "
        "precipitated out and the MgSO4 is left in solution.",
        f"Remaining hardness = {n(mol_mgso4, 5)} x {n(mm_caco3_h)} = "
        f"{n(mol_mgso4 * mm_caco3_h, 3)} g/dm3 = {n(ppm_after_boiling)} ppm, "
        "and it is permanent hardness, needing washing soda or an ion-exchange "
        "column to remove it.",
    ],
    answer=(
        f"(a) {n(total_hardness_mol, 5)} mol/dm3  "
        f"(b) {n(ppm_total)} ppm as CaCO3  "
        f"(c) {n(ppm_after_boiling)} ppm of permanent hardness"
    ),
))


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    names = [name for name, _ in EXAMPLES]
    if len(set(names)) != len(names):
        raise SystemExit("two examples share a filename")
    for name, text in EXAMPLES:
        (ROOT / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(EXAMPLES)} worked examples to {ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
