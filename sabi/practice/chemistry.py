"""Chemistry practice templates.

Same discipline as the other two: the numbers are sampled, the answer is
computed, and every constant used is stated in the question, because that is
how the Chemistry corpus states them.

One rule specific to this subject: **no relative molecular mass is typed.**
Each compound is declared as its composition and its mass is summed from the
atomic masses in `RAM`, so a template cannot disagree with the corpus about
what H2SO4 weighs. `RAM` is the table `CHM A0` publishes, which is also the
table the worked examples use.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from fractions import Fraction

from sabi.practice.templates import Built, n, template

SUBJECT = "Chemistry"

# The relative atomic masses CHM A0 supplies. Chlorine is the only one that is
# not a whole number, so the table is exact rather than floating point.
RAM: dict[str, Fraction] = {
    "H": Fraction(1), "C": Fraction(12), "N": Fraction(14), "O": Fraction(16),
    "Na": Fraction(23), "Mg": Fraction(24), "S": Fraction(32),
    "Cl": Fraction(71, 2), "K": Fraction(39), "Ca": Fraction(40),
    "Fe": Fraction(56), "Cu": Fraction(64), "Zn": Fraction(65),
    "Ag": Fraction(108),
}

# Molar volume at s.t.p., in dm3 per mole, and the Faraday constant in
# coulombs per mole of electrons. Both are stated in every question that uses
# them, as the corpus does.
MOLAR_VOLUME = Fraction(224, 10)
FARADAY = 96500


@dataclass(frozen=True)
class Compound:
    """A formula, and the composition its mass is summed from."""

    formula: str
    name: str
    composition: tuple[tuple[str, int], ...]

    @property
    def mass(self) -> Fraction:
        return sum((RAM[el] * count for el, count in self.composition), Fraction(0))

    @property
    def working(self) -> str:
        parts = " + ".join(
            f"{count} x {n(RAM[el])}" if count > 1 else n(RAM[el])
            for el, count in self.composition
        )
        return f"{parts} = {n(self.mass)}"


COMPOUNDS: dict[str, Compound] = {
    c.formula: c
    for c in [
        Compound("NaOH", "sodium hydroxide", (("Na", 1), ("O", 1), ("H", 1))),
        Compound("KOH", "potassium hydroxide", (("K", 1), ("O", 1), ("H", 1))),
        Compound("HCl", "hydrochloric acid", (("H", 1), ("Cl", 1))),
        Compound("H2SO4", "tetraoxosulphate(VI) acid", (("H", 2), ("S", 1), ("O", 4))),
        Compound("CaCO3", "calcium trioxocarbonate(IV)", (("Ca", 1), ("C", 1), ("O", 3))),
        Compound("Na2CO3", "sodium trioxocarbonate(IV)", (("Na", 2), ("C", 1), ("O", 3))),
        Compound("NaCl", "sodium chloride", (("Na", 1), ("Cl", 1))),
        Compound("KCl", "potassium chloride", (("K", 1), ("Cl", 1))),
        Compound("CaO", "calcium oxide", (("Ca", 1), ("O", 1))),
        Compound("MgO", "magnesium oxide", (("Mg", 1), ("O", 1))),
        Compound("CuO", "copper(II) oxide", (("Cu", 1), ("O", 1))),
        Compound("ZnO", "zinc oxide", (("Zn", 1), ("O", 1))),
        Compound("CO2", "carbon(IV) oxide", (("C", 1), ("O", 2))),
        Compound("H2O", "water", (("H", 2), ("O", 1))),
        Compound("CuSO4", "copper(II) tetraoxosulphate(VI)",
                 (("Cu", 1), ("S", 1), ("O", 4))),
        Compound("MgSO4", "magnesium tetraoxosulphate(VI)",
                 (("Mg", 1), ("S", 1), ("O", 4))),
        Compound("Ca(OH)2", "calcium hydroxide", (("Ca", 1), ("O", 2), ("H", 2))),
        Compound("AgNO3", "silver trioxonitrate(V)",
                 (("Ag", 1), ("N", 1), ("O", 3))),
    ]
}

# Fractions of a mole that keep a mass whole for every compound above, since
# each of those masses is either an integer or a half.
NICE_MOLES = [
    Fraction(1, 4), Fraction(1, 2), Fraction(1), Fraction(3, 2),
    Fraction(2), Fraction(5, 2), Fraction(3), Fraction(4), Fraction(5),
]


def _pick(rng, formulas: list[str]) -> str:
    return rng.choice(formulas)


# ------------------------------------------------------- the mole concept


@template(
    "moles-from-mass",
    doc="chm-ex-01-moles-from-mass",
    locator="CEX 1",
    topic="Quantitative chemistry",
    subtopic="Mole concept and stoichiometry",
    subject=SUBJECT,
)
def moles_from_mass(rng, params=None) -> Built:
    if params is None:
        params = {
            "formula": _pick(rng, list(COMPOUNDS)),
            "moles_num": 0,
            "moles_den": 1,
        }
        chosen = rng.choice(NICE_MOLES)
        params["moles_num"], params["moles_den"] = chosen.numerator, chosen.denominator
    compound = COMPOUNDS[params["formula"]]
    moles = Fraction(params["moles_num"], params["moles_den"])

    mass = moles * compound.mass

    return Built(
        params=params,
        question=(
            f"Calculate the number of moles in {n(mass)} g of "
            f"{compound.name}, {compound.formula}. "
            f"[{_ram_note(compound)}]"
        ),
        answer=n(moles),
        hint="Give the number of moles.",
        working=(
            f"Relative molecular mass of {compound.formula} = "
            f"{compound.working} g/mol.",
            f"Number of moles = mass / molar mass = {n(mass)} / {n(compound.mass)}.",
            f"= {n(moles)} mol.",
        ),
    )


@template(
    "mass-from-moles",
    doc="chm-ex-01-moles-from-mass",
    locator="CEX 1",
    topic="Quantitative chemistry",
    subtopic="Mole concept and stoichiometry",
    subject=SUBJECT,
)
def mass_from_moles(rng, params=None) -> Built:
    if params is None:
        chosen = rng.choice(NICE_MOLES)
        params = {
            "formula": _pick(rng, list(COMPOUNDS)),
            "moles_num": chosen.numerator,
            "moles_den": chosen.denominator,
        }
    compound = COMPOUNDS[params["formula"]]
    moles = Fraction(params["moles_num"], params["moles_den"])

    mass = moles * compound.mass

    return Built(
        params=params,
        question=(
            f"What is the mass of {n(moles)} mol of {compound.name}, "
            f"{compound.formula}? [{_ram_note(compound)}]"
        ),
        answer=n(mass),
        hint="Give the mass in grams.",
        working=(
            f"Relative molecular mass of {compound.formula} = "
            f"{compound.working} g/mol.",
            f"Mass = moles x molar mass = {n(moles)} x {n(compound.mass)}.",
            f"= {n(mass)} g.",
        ),
    )


@template(
    "relative-molecular-mass",
    doc="chm-ex-19-relative-molecular-mass",
    locator="CEX 19",
    topic="Quantitative chemistry",
    subtopic="Mole concept and stoichiometry",
    subject=SUBJECT,
)
def relative_molecular_mass(rng, params=None) -> Built:
    if params is None:
        params = {"formula": _pick(rng, list(COMPOUNDS))}
    compound = COMPOUNDS[params["formula"]]

    return Built(
        params=params,
        question=(
            f"Calculate the relative molecular mass of {compound.name}, "
            f"{compound.formula}. [{_ram_note(compound)}]"
        ),
        answer=n(compound.mass),
        hint="Give the relative molecular mass.",
        working=(
            "Add the relative atomic mass of every atom in the formula.",
            f"{compound.formula}: {compound.working}.",
            f"Relative molecular mass = {n(compound.mass)}.",
        ),
    )


@template(
    "moles-from-gas-volume",
    doc="chm-ex-02-moles-from-gas-volume",
    locator="CEX 2",
    topic="Quantitative chemistry",
    subtopic="Mole concept and stoichiometry",
    subject=SUBJECT,
)
def moles_from_gas_volume(rng, params=None) -> Built:
    if params is None:
        # Quarters of a mole, so the volume lands on one decimal place.
        params = {"quarters": rng.choice([1, 2, 3, 4, 6, 8, 10]),
                  "formula": _pick(rng, ["CO2", "H2O"])}
    moles = Fraction(params["quarters"], 4)
    gas = "carbon(IV) oxide, CO2" if params["formula"] == "CO2" else "steam"

    volume = moles * MOLAR_VOLUME

    return Built(
        params=params,
        question=(
            f"How many moles are there in {n(volume)} dm3 of {gas} at s.t.p.? "
            f"[Molar volume at s.t.p. = 22.4 dm3/mol]"
        ),
        answer=n(moles),
        hint="Give the number of moles.",
        working=(
            "At s.t.p. one mole of any gas occupies 22.4 dm3.",
            f"Number of moles = volume / 22.4 = {n(volume)} / 22.4.",
            f"= {n(moles)} mol.",
        ),
    )


def _ram_note(compound: Compound) -> str:
    """The relative atomic masses a question needs, in the corpus's style."""
    parts = sorted({el for el, _ in compound.composition})
    return ", ".join(f"{el} = {n(RAM[el])}" for el in parts)


# ----------------------------------------------------------- solutions


@template(
    "concentration-mol-per-dm3",
    doc="chm-ex-07-concentration-mol-per-dm3",
    locator="CEX 7",
    topic="Quantitative chemistry",
    subtopic="Solutions and solubility",
    subject=SUBJECT,
)
def concentration_mol_per_dm3(rng, params=None) -> Built:
    if params is None:
        params = {
            "formula": _pick(rng, ["NaOH", "KOH", "HCl", "NaCl", "Na2CO3"]),
            "volume_cm3": rng.choice([100, 200, 250, 400, 500]),
            "moles_hundredths": rng.choice([5, 10, 20, 25, 40, 50]),
        }
    compound = COMPOUNDS[params["formula"]]
    volume = Fraction(params["volume_cm3"], 1000)
    moles = Fraction(params["moles_hundredths"], 100)

    mass = moles * compound.mass
    concentration = moles / volume

    return Built(
        params=params,
        question=(
            f"{n(mass)} g of {compound.name}, {compound.formula}, is dissolved "
            f"in water and made up to {params['volume_cm3']} cm3 of solution. "
            f"Calculate the concentration in mol/dm3. [{_ram_note(compound)}]"
        ),
        answer=n(concentration),
        hint="Give the concentration in mol/dm3.",
        working=(
            f"Relative molecular mass of {compound.formula} = "
            f"{compound.working} g/mol.",
            f"Moles = {n(mass)} / {n(compound.mass)} = {n(moles)} mol.",
            f"Volume = {params['volume_cm3']}/1000 = {n(volume)} dm3, so "
            f"concentration = {n(moles)} / {n(volume)} = "
            f"{n(concentration)} mol/dm3.",
        ),
    )


@template(
    "concentration-g-per-dm3",
    doc="chm-ex-08-concentration-g-per-dm3",
    locator="CEX 8",
    topic="Quantitative chemistry",
    subtopic="Solutions and solubility",
    subject=SUBJECT,
)
def concentration_g_per_dm3(rng, params=None) -> Built:
    if params is None:
        params = {
            "formula": _pick(rng, ["NaOH", "KOH", "HCl", "H2SO4", "Na2CO3", "NaCl"]),
            "conc_hundredths": rng.choice([10, 20, 25, 50, 100, 150, 200]),
        }
    compound = COMPOUNDS[params["formula"]]
    molar = Fraction(params["conc_hundredths"], 100)

    grams = molar * compound.mass

    return Built(
        params=params,
        question=(
            f"A solution of {compound.name}, {compound.formula}, has a "
            f"concentration of {n(molar)} mol/dm3. Express this in g/dm3. "
            f"[{_ram_note(compound)}]"
        ),
        answer=n(grams),
        hint="Give the concentration in g/dm3.",
        working=(
            "Concentration in g/dm3 = concentration in mol/dm3 x molar mass.",
            f"Molar mass of {compound.formula} = {compound.working} g/mol.",
            f"= {n(molar)} x {n(compound.mass)} = {n(grams)} g/dm3.",
        ),
    )


@template(
    "dilution",
    doc="chm-ex-09-dilution",
    locator="CEX 9",
    topic="Quantitative chemistry",
    subtopic="Solutions and solubility",
    subject=SUBJECT,
)
def dilution(rng, params=None) -> Built:
    if params is None:
        params = {
            "start_hundredths": rng.choice([20, 25, 40, 50, 100, 200]),
            "from_cm3": rng.choice([20, 25, 50, 100]),
            "factor": rng.choice([2, 4, 5, 10]),
        }
    start = Fraction(params["start_hundredths"], 100)
    from_cm3 = params["from_cm3"]
    to_cm3 = from_cm3 * params["factor"]

    final = start * Fraction(from_cm3, to_cm3)

    return Built(
        params=params,
        question=(
            f"{from_cm3} cm3 of a {n(start)} mol/dm3 solution is diluted with "
            f"water to {to_cm3} cm3. Calculate the concentration of the "
            f"diluted solution."
        ),
        answer=n(final),
        hint="Give the concentration in mol/dm3.",
        working=(
            "Diluting adds water but not solute, so the moles are unchanged: "
            "C1V1 = C2V2.",
            f"{n(start)} x {from_cm3} = C2 x {to_cm3}.",
            f"C2 = {n(final)} mol/dm3.",
        ),
    )


@template(
    "titration-concentration",
    doc="chm-ex-10-titration",
    locator="CEX 10",
    topic="Quantitative chemistry",
    subtopic="Volumetric analysis",
    subject=SUBJECT,
)
def titration_concentration(rng, params=None) -> Built:
    if params is None:
        params = {
            "base_cm3": rng.choice([20, 25]),
            "base_hundredths": rng.choice([10, 20, 25, 50]),
            "acid_cm3": rng.choice([10, 20, 25, 40, 50]),
            "ratio": rng.choice([1, 2]),
        }
    base_cm3 = params["base_cm3"]
    base_conc = Fraction(params["base_hundredths"], 100)
    acid_cm3 = params["acid_cm3"]
    ratio = params["ratio"]

    base_moles = base_conc * Fraction(base_cm3, 1000)
    acid_moles = base_moles * ratio
    acid_conc = acid_moles / Fraction(acid_cm3, 1000)

    if ratio == 2:
        equation = "Na2CO3 + 2HCl -> 2NaCl + H2O + CO2"
        base = "sodium trioxocarbonate(IV), Na2CO3"
    else:
        equation = "NaOH + HCl -> NaCl + H2O"
        base = "sodium hydroxide, NaOH"

    return Built(
        params=params,
        question=(
            f"{base_cm3} cm3 of {n(base_conc)} mol/dm3 {base} required "
            f"{acid_cm3} cm3 of hydrochloric acid for complete "
            f"neutralisation. The equation is {equation}. Calculate the "
            f"concentration of the acid in mol/dm3."
        ),
        answer=n(acid_conc),
        hint="Give the concentration of the acid in mol/dm3.",
        working=(
            f"Moles of base = {n(base_conc)} x {base_cm3}/1000 = "
            f"{n(base_moles)} mol.",
            f"The equation shows {ratio} mol of acid per mole of base, so "
            f"moles of acid = {n(acid_moles)} mol.",
            f"Concentration = {n(acid_moles)} / ({acid_cm3}/1000) = "
            f"{n(acid_conc)} mol/dm3.",
        ),
    )


# ------------------------------------------------------- purity and yield


@template(
    "percentage-purity",
    doc="chm-ex-11-percentage-purity",
    locator="CEX 11",
    topic="Quantitative chemistry",
    subtopic="Mole concept and stoichiometry",
    subject=SUBJECT,
)
def percentage_purity(rng, params=None) -> Built:
    if params is None:
        params = {
            "sample": rng.choice([20, 25, 40, 50, 80, 100, 200]),
            "percent": rng.choice([40, 50, 60, 75, 80, 90, 95]),
        }
    sample, percent = params["sample"], params["percent"]
    pure = Fraction(sample * percent, 100)

    return Built(
        params=params,
        question=(
            f"A {n(sample)} g sample of impure calcium trioxocarbonate(IV) "
            f"was found to contain {n(pure)} g of the pure compound. "
            f"Calculate the percentage purity of the sample."
        ),
        answer=n(Fraction(percent)),
        hint="Give the percentage, without the % sign.",
        working=(
            "Percentage purity = (mass of pure compound / mass of sample) "
            "x 100.",
            f"= ({n(pure)} / {n(sample)}) x 100.",
            f"= {percent} per cent.",
        ),
    )


@template(
    "percentage-yield",
    doc="chm-ex-12-percentage-yield",
    locator="CEX 12",
    topic="Quantitative chemistry",
    subtopic="Mole concept and stoichiometry",
    subject=SUBJECT,
)
def percentage_yield(rng, params=None) -> Built:
    if params is None:
        params = {
            "theoretical": rng.choice([20, 25, 40, 50, 80, 100, 200]),
            "percent": rng.choice([40, 50, 60, 75, 80, 90]),
        }
    theoretical, percent = params["theoretical"], params["percent"]
    actual = Fraction(theoretical * percent, 100)

    return Built(
        params=params,
        question=(
            f"A reaction that should give {n(theoretical)} g of product "
            f"actually gives {n(actual)} g. Calculate the percentage yield."
        ),
        answer=n(Fraction(percent)),
        hint="Give the percentage, without the % sign.",
        working=(
            "Percentage yield = (actual yield / theoretical yield) x 100.",
            f"= ({n(actual)} / {n(theoretical)}) x 100.",
            f"= {percent} per cent.",
        ),
    )


# --------------------------------------------------- reactions and energy


@template(
    "electrolysis-mass",
    doc="chm-ex-15-electrolysis-faraday",
    locator="CEX 15",
    topic="Chemical reactions",
    subtopic="Electrolysis",
    subject=SUBJECT,
)
def electrolysis_mass(rng, params=None) -> Built:
    if params is None:
        # Charge is chosen as a whole number of faradays over ten, so the
        # moles of electrons land on one decimal place.
        params = {
            "current": rng.choice([2, 4, 5, 10]),
            "tenths_of_faraday": rng.choice([1, 2, 4, 5]),
            "metal": rng.choice(["Cu", "Zn", "Ag"]),
        }
    current = params["current"]
    electron_moles = Fraction(params["tenths_of_faraday"], 10)
    metal = params["metal"]
    charge_z = 1 if metal == "Ag" else 2
    names = {"Cu": "copper", "Zn": "zinc", "Ag": "silver"}

    charge = electron_moles * FARADAY
    seconds = charge / current
    metal_moles = electron_moles / charge_z
    mass = metal_moles * RAM[metal]

    ion = f"{metal}{'+' if charge_z == 1 else '2+'}"
    return Built(
        params=params,
        question=(
            f"A current of {current} A is passed for {n(seconds)} s through a "
            f"solution containing {ion} ions. Calculate the mass of "
            f"{names[metal]} deposited at the cathode. The cathode reaction is "
            f"{ion} + {charge_z}e- -> {metal}. "
            f"[{metal} = {n(RAM[metal])}; 1 faraday = 96500 C/mol]"
        ),
        answer=n(mass),
        hint="Give the mass in grams.",
        working=(
            f"Quantity of charge = I x t = {current} x {n(seconds)} = "
            f"{n(charge)} C.",
            f"Moles of electrons = {n(charge)} / 96500 = "
            f"{n(electron_moles)} mol.",
            f"The equation needs {charge_z} mol of electrons per mole of "
            f"{names[metal]}, so mass = ({n(electron_moles)}/{charge_z}) x "
            f"{n(RAM[metal])} = {n(mass)} g.",
        ),
    )


@template(
    "heat-of-reaction",
    doc="chm-ex-16-heat-of-reaction",
    locator="CEX 16",
    topic="Chemical reactions",
    subtopic="Energy changes",
    subject=SUBJECT,
)
def heat_of_reaction(rng, params=None) -> Built:
    if params is None:
        params = {
            "mass_g": rng.choice([100, 150, 200, 250, 400, 500]),
            "rise_tenths": rng.choice([25, 40, 50, 68, 80, 100, 125]),
        }
    mass_g = params["mass_g"]
    rise = Fraction(params["rise_tenths"], 10)

    # 4.2 J per gram per kelvin, the value CHM A0 publishes.
    heat = Fraction(mass_g) * Fraction(42, 10) * rise

    return Built(
        params=params,
        question=(
            f"{mass_g} cm3 of solution is warmed by a reaction and its "
            f"temperature rises by {n(rise)} degrees Celsius. Calculate the "
            f"heat given out. [Take the density of the solution as 1 g/cm3 "
            f"and its specific heat capacity as 4.2 J/g/K]"
        ),
        answer=n(heat),
        hint="Give the heat energy in joules.",
        working=(
            f"The density is 1 g/cm3, so {mass_g} cm3 has a mass of "
            f"{mass_g} g.",
            f"Q = mc(change in temperature) = {mass_g} x 4.2 x {n(rise)}.",
            f"Q = {n(heat)} J.",
        ),
    )


@template(
    "rate-of-reaction",
    doc="chm-ex-17-rate-of-reaction",
    locator="CEX 17",
    topic="Chemical reactions",
    subtopic="Rates of reaction",
    subject=SUBJECT,
)
def rate_of_reaction(rng, params=None) -> Built:
    if params is None:
        params = {
            "start_hundredths": rng.choice([50, 60, 80, 100, 150, 200]),
            "drop_hundredths": rng.choice([10, 20, 25, 30, 40]),
            # 60 is excluded: its factor of 3 turns a rate like 0.10/60 into
            # 1/600, which is a fine rate and a poor thing to ask a student
            # to type. Every value here divides a power of ten.
            "seconds": rng.choice([10, 20, 25, 40, 50, 100]),
        }
    start = Fraction(params["start_hundredths"], 100)
    drop = Fraction(params["drop_hundredths"], 100)
    seconds = params["seconds"]
    end = start - drop

    rate = drop / seconds

    return Built(
        params=params,
        question=(
            f"The concentration of a reactant falls from {n(start)} mol/dm3 "
            f"to {n(end)} mol/dm3 in {seconds} s. Calculate the average rate "
            f"of reaction."
        ),
        answer=n(rate),
        hint="Give the rate in mol/dm3 per second.",
        working=(
            "Average rate = change in concentration / time taken.",
            f"Change = {n(start)} - {n(end)} = {n(drop)} mol/dm3.",
            f"Rate = {n(drop)} / {seconds} = {n(rate)} mol/dm3 per second.",
        ),
    )


@template(
    "gas-law-volume",
    doc="chm-ex-20-general-gas-law",
    locator="CEX 20",
    topic="Quantitative chemistry",
    subtopic="Gas laws",
    subject=SUBJECT,
)
def gas_law_volume(rng, params=None) -> Built:
    if params is None:
        params = {
            "volume": rng.choice([200, 240, 300, 380, 400, 500, 600]),
            "celsius": rng.choice([27, 57, 87, 127]),
            "pressure": rng.choice([700, 720, 750, 800, 900]),
        }
    volume = params["volume"]
    celsius = params["celsius"]
    kelvin = celsius + 273
    pressure = params["pressure"]

    # Corrected to s.t.p.: 273 K and 760 mmHg.
    corrected = (
        Fraction(pressure * volume, kelvin) * Fraction(273) / Fraction(760)
    )

    return Built(
        params=params,
        question=(
            f"{volume} cm3 of a gas is collected at {celsius} degrees Celsius "
            f"and {pressure} mmHg. Calculate its volume at s.t.p., which is "
            f"273 K and 760 mmHg. Give your answer to one decimal place."
        ),
        answer=n(float(corrected), places=1),
        hint="Give the volume in cm3, to one decimal place.",
        working=(
            "The general gas equation is P1V1/T1 = P2V2/T2, with temperatures "
            "in kelvin.",
            f"T1 = {celsius} + 273 = {kelvin} K.",
            f"V2 = ({pressure} x {volume} x 273) / ({kelvin} x 760) = "
            f"{n(float(corrected), places=1)} cm3.",
        ),
    )
