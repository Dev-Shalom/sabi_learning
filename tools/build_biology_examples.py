#!/usr/bin/env python
"""Generate the Biology worked examples, with every numeric answer computed.

Same reasoning as `tools/build_physics_examples.py`: a worked example with a
typo in its final line is the kind of wrong that is hardest to catch by
reading, so no number in the output is typed. Each example states its givens,
the arithmetic is done here, and the stated answer is formatted from the
computed value.

Biology differs from Physics in one way that matters. Many of its questions
are structural -- explain, compare, describe a process -- and have no number
in them at all. Inventing one to make the example look rigorous would be
exactly the failure this corpus exists to avoid. Those examples are built with
``numeric=False``: they end in a bold sentence, not a bold figure, and they
are written without digits anywhere in the prose so that
`tests/test_biology_corpus.py` can prove no unsupported figure crept in.

`tests/test_biology_corpus.py` then recomputes every numeric example
independently from the markdown, sharing no code with this file.

    python tools/build_biology_examples.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "corpus" / "biology" / "examples"


def n(value: float, dp: int = 2) -> str:
    """A number as a student would write it: no trailing zeros, no -0."""
    rounded = round(value + 0.0, dp)
    if rounded == int(rounded):
        return str(int(rounded))
    text = f"{rounded:.{dp}f}".rstrip("0").rstrip(".")
    return text if text != "-0" else "0"


EXAMPLES: list[tuple[str, str]] = []
NUMERIC: list[str] = []
EXPLANATORY: list[str] = []


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
    numeric: bool,
) -> tuple[str, str]:
    """One worked example, in the same shape as the Physics corpus.

    ``numeric`` records which kind of example this is. A structural example
    must carry no digit outside the step numbering, because nothing in it
    would support one.
    """
    doc_id = f"bio-ex-{num:02d}-{slug}"
    body = "\n".join(f"{i}. {line}" for i, line in enumerate(steps, start=1))

    if not numeric:
        prose = "\n".join([question, *steps, answer])
        stray = [c for c in prose if c.isdigit()]
        assert not stray, (
            f"{doc_id} is a structural example but carries digits {stray!r}; "
            "either it is really a calculation, or that figure has nothing "
            "behind it"
        )
        EXPLANATORY.append(doc_id)
    else:
        NUMERIC.append(doc_id)

    text = f"""---
doc_id: {doc_id}
title: {title}
source: Sabi worked example, WAEC Paper 2 style
attribution: worked_example
topic: {topic}
subtopic: {subtopic}
syllabus_section: {section}
exam_board: WAEC
subject: Biology
level: SS3
locator: BEX {num}
---

## Question

{question}

## Solution

{body}

**Answer: {answer}**
"""
    return f"{doc_id}.md", text


# ------------------------------------------------ 1. magnification of a cell
image_mm, object_mm = 30.0, 0.05
magnification = image_mm / object_mm
EXAMPLES.append(doc(
    num=1, slug="magnification-of-a-cell",
    title="Magnification from image size and actual size",
    topic="Cell structure and organisation", subtopic="Using the microscope",
    section="A2", numeric=True,
    question=(
        f"Under a microscope the image of a cheek cell measures {n(image_mm)} mm "
        f"across. The actual width of the cell is {n(object_mm)} mm. Find the "
        "magnification."
    ),
    steps=[
        "Magnification = size of image ÷ size of the actual object. The two "
        "sizes must be in the same unit, and here both are already in mm.",
        f"Magnification = {n(image_mm)} ÷ {n(object_mm)}.",
        f"Magnification = ×{n(magnification)}.",
        "Magnification has no unit: it is a ratio of two lengths, so the units "
        "cancel. Write it with a multiplication sign, not with mm.",
    ],
    answer=f"×{n(magnification)}",
))

# --------------------------------------------- 2. magnification of a drawing
drawing_mm, specimen_mm = 135.0, 45.0
draw_mag = drawing_mm / specimen_mm
seed_drawing_mm, seed_mag = 60.0, 5.0
seed_actual = seed_drawing_mm / seed_mag
EXAMPLES.append(doc(
    num=2, slug="drawing-magnification",
    title="Linear magnification of a biological drawing",
    topic="Cell structure and organisation", subtopic="Biological drawing",
    section="A2", numeric=True,
    question=(
        f"(a) A student's drawing of a locust is {n(drawing_mm)} mm long. The "
        f"locust itself is {n(specimen_mm)} mm long. Find the linear "
        "magnification of the drawing. "
        f"(b) Another drawing, labelled ×{n(seed_mag)}, shows a seed "
        f"{n(seed_drawing_mm)} mm long. Find the actual length of the seed."
    ),
    steps=[
        "Part (a). Linear magnification = length of drawing ÷ length of "
        "specimen, with both lengths measured along the same line.",
        f"Magnification = {n(drawing_mm)} ÷ {n(specimen_mm)} = ×{n(draw_mag)}.",
        "Part (b). Rearranging the same relation, actual length = length of "
        "drawing ÷ magnification.",
        f"Actual length = {n(seed_drawing_mm)} ÷ {n(seed_mag)} = "
        f"{n(seed_actual)} mm.",
        "In a biological drawing measure the greatest length of the specimen "
        "and the matching length on the drawing; measuring two different "
        "features gives a meaningless ratio.",
    ],
    answer=f"(a) ×{n(draw_mag)}  (b) {n(seed_actual)} mm",
))

# ----------------------------------------- 3. surface area to volume ratio
small_side, large_side = 1.0, 3.0
small_area, small_vol = 6 * small_side ** 2, small_side ** 3
large_area, large_vol = 6 * large_side ** 2, large_side ** 3
small_ratio = small_area / small_vol
large_ratio = large_area / large_vol
EXAMPLES.append(doc(
    num=3, slug="surface-area-to-volume",
    title="Surface area to volume ratio of two model cells",
    topic="The cell and its environment", subtopic="Exchange of materials",
    section="A1", numeric=True,
    question=(
        f"Two cubes of agar are cut, one of side {n(small_side)} cm and one of "
        f"side {n(large_side)} cm. Find the surface area to volume ratio of "
        "each, and say which would absorb a dissolved substance more quickly "
        "for its size."
    ),
    steps=[
        "A cube has six square faces, so surface area = 6 × side², and "
        "volume = side³.",
        f"Small cube: surface area = 6 × {n(small_side)}² = {n(small_area)} cm²; "
        f"volume = {n(small_side)}³ = {n(small_vol)} cm³.",
        f"Ratio = {n(small_area)} ÷ {n(small_vol)} = {n(small_ratio)}, that is "
        f"{n(small_ratio)}:1.",
        f"Large cube: surface area = 6 × {n(large_side)}² = {n(large_area)} cm²; "
        f"volume = {n(large_side)}³ = {n(large_vol)} cm³.",
        f"Ratio = {n(large_area)} ÷ {n(large_vol)} = {n(large_ratio)}, that is "
        f"{n(large_ratio)}:1.",
        "The smaller cube has the larger ratio, so it has more surface for "
        "every unit of volume and takes up the substance faster for its size. "
        "This is why cells stay small, and why large organisms need "
        "specialised exchange surfaces such as lungs and gills.",
    ],
    answer=(
        f"small cube {n(small_ratio)}:1, large cube {n(large_ratio)}:1; the "
        "smaller cube absorbs faster for its size"
    ),
))

# ------------------------------------------------------ 4. monohybrid cross
f2_total = 480.0
f2_tall = f2_total * 3 / 4
f2_dwarf = f2_total * 1 / 4
EXAMPLES.append(doc(
    num=4, slug="monohybrid-cross",
    title="F2 ratio and numbers from a monohybrid cross",
    topic="Genetics and variation", subtopic="Monohybrid inheritance",
    section="F1", numeric=True,
    question=(
        "In a certain plant, tallness (T) is dominant to dwarfness (t). A "
        "pure-breeding tall plant is crossed with a pure-breeding dwarf plant, "
        f"and the F1 plants are then selfed. Out of {n(f2_total)} F2 plants, "
        "how many would be expected to be tall and how many dwarf?"
    ),
    steps=[
        "Parents: TT (tall) × tt (dwarf). Each parent makes only one kind of "
        "gamete, T from one and t from the other.",
        "F1: every plant is Tt. T is dominant, so all the F1 plants are tall.",
        "Selfing the F1 means Tt × Tt. Each parent makes T and t gametes in "
        "equal numbers.",
        "The Punnett square gives TT, Tt, Tt, tt — a genotypic ratio of "
        "1 TT : 2 Tt : 1 tt.",
        "TT and Tt both show the dominant character, so the phenotypic ratio "
        "is 3 tall : 1 dwarf.",
        f"Expected tall = 3/4 × {n(f2_total)} = {n(f2_tall)}.",
        f"Expected dwarf = 1/4 × {n(f2_total)} = {n(f2_dwarf)}.",
        "These are expected numbers. Real counts scatter about them, because "
        "which gamete meets which is a matter of chance.",
    ],
    answer=f"{n(f2_tall)} tall and {n(f2_dwarf)} dwarf, a ratio of 3:1",
))

# ------------------------------------------------------------- 5. test cross
tc_total = 96.0
tc_tall = tc_total / 2
tc_dwarf = tc_total / 2
EXAMPLES.append(doc(
    num=5, slug="test-cross",
    title="Finding an unknown genotype by a test cross",
    topic="Genetics and variation", subtopic="Test cross",
    section="F1", numeric=True,
    question=(
        "A tall plant may be TT or Tt. It is crossed with a dwarf plant (tt) "
        f"and {n(tc_total)} offspring are raised. State the two possible "
        "results and the numbers expected in each, and say what each result "
        "shows about the tall parent."
    ),
    steps=[
        "A test cross means crossing the individual of unknown genotype with "
        "the homozygous recessive, here tt. The dwarf parent can only "
        "contribute t, so every offspring shows whatever the tall parent gave "
        "it.",
        "Possibility one: the tall parent is TT. It makes only T gametes, so "
        "every offspring is Tt and therefore tall.",
        f"Expected result: all {n(tc_total)} offspring tall, none dwarf.",
        "Possibility two: the tall parent is Tt. It makes T and t gametes in "
        "equal numbers, so the offspring are Tt and tt in equal numbers — a "
        "ratio of 1 tall : 1 dwarf.",
        f"Expected result: {n(tc_tall)} tall and {n(tc_dwarf)} dwarf.",
        "So a single dwarf offspring is enough to prove the tall parent "
        "heterozygous, because a dwarf offspring must have received t from "
        "each parent.",
    ],
    answer=(
        f"if TT, all {n(tc_total)} offspring tall; if Tt, {n(tc_tall)} tall "
        f"and {n(tc_dwarf)} dwarf in a 1:1 ratio"
    ),
))

# -------------------------------------------------------- 6. dihybrid cross
dh_total = 640.0
dh_round_yellow = dh_total * 9 / 16
dh_round_green = dh_total * 3 / 16
dh_wrinkled_yellow = dh_total * 3 / 16
dh_wrinkled_green = dh_total * 1 / 16
EXAMPLES.append(doc(
    num=6, slug="dihybrid-cross",
    title="Phenotypes expected from a dihybrid cross",
    topic="Genetics and variation", subtopic="Dihybrid inheritance",
    section="F1", numeric=True,
    question=(
        "In garden pea, round seed (R) is dominant to wrinkled (r) and yellow "
        "cotyledon (Y) is dominant to green (y). Two plants, each heterozygous "
        f"for both characters, are crossed. Out of {n(dh_total)} seeds, how "
        "many of each phenotype would be expected?"
    ),
    steps=[
        "Both parents are RrYy. With the two genes on different chromosomes, "
        "each parent makes four kinds of gamete in equal numbers: RY, Ry, rY "
        "and ry.",
        "A four-by-four Punnett square therefore has sixteen boxes, each "
        "equally likely.",
        "Counting the boxes gives the classic phenotypic ratio "
        "9 round yellow : 3 round green : 3 wrinkled yellow : 1 wrinkled green.",
        f"One sixteenth of {n(dh_total)} is {n(dh_total/16)}, so multiply each "
        "part of the ratio by that.",
        f"Round yellow = 9/16 × {n(dh_total)} = {n(dh_round_yellow)}.",
        f"Round green = 3/16 × {n(dh_total)} = {n(dh_round_green)}.",
        f"Wrinkled yellow = 3/16 × {n(dh_total)} = {n(dh_wrinkled_yellow)}.",
        f"Wrinkled green = 1/16 × {n(dh_total)} = {n(dh_wrinkled_green)}.",
        "The two new combinations, round green and wrinkled yellow, appear "
        "because the two pairs of alleles are inherited independently of each "
        "other.",
    ],
    answer=(
        f"{n(dh_round_yellow)} round yellow, {n(dh_round_green)} round green, "
        f"{n(dh_wrinkled_yellow)} wrinkled yellow, {n(dh_wrinkled_green)} "
        "wrinkled green (9:3:3:1)"
    ),
))

# ------------------------------------------------- 7. sex-linked inheritance
cb_any_child = 1 / 4 * 100
cb_sons = 1 / 2 * 100
EXAMPLES.append(doc(
    num=7, slug="sex-linked-inheritance",
    title="Probability of colour blindness in the children of a carrier",
    topic="Genetics and variation", subtopic="Sex linkage",
    section="F1", numeric=True,
    question=(
        "Red-green colour blindness is caused by a recessive allele carried on "
        "the X chromosome. A woman with normal vision whose father was colour "
        "blind marries a man with normal vision. Find (a) the probability that "
        "any one of their children is colour blind, (b) the probability that a "
        "son is colour blind."
    ),
    steps=[
        "Write the alleles on the chromosomes. Use X^B for the normal allele "
        "and X^b for the colour-blind allele. The Y chromosome carries "
        "neither.",
        "The woman's father was colour blind, so he was X^b Y and gave his "
        "only X, carrying X^b, to every daughter. She has normal vision, so "
        "she is X^B X^b: a carrier.",
        "The husband has normal vision, so he is X^B Y.",
        "Cross X^B X^b × X^B Y. The four equally likely offspring are "
        "X^B X^B, X^B X^b, X^B Y and X^b Y.",
        "Only X^b Y is colour blind, because a boy has no second X to mask the "
        "recessive allele.",
        f"Part (a). One of the four outcomes is colour blind, so the "
        f"probability is 1/4 = {n(cb_any_child)}%.",
        "Part (b). Restricting attention to the sons, there are two: X^B Y and "
        "X^b Y.",
        f"One of those two is colour blind, so the probability is 1/2 = "
        f"{n(cb_sons)}%.",
        "None of the daughters is colour blind, but half of them are carriers.",
    ],
    answer=f"(a) 1/4, that is {n(cb_any_child)}%  (b) 1/2, that is {n(cb_sons)}%",
))

# ------------------------------------------------ 8. blood group inheritance
bg_each = 1 / 4 * 100
EXAMPLES.append(doc(
    num=8, slug="blood-group-inheritance",
    title="Blood groups possible among the children of an A and a B parent",
    topic="Genetics and variation", subtopic="Multiple alleles",
    section="F1", numeric=True,
    question=(
        "A man of blood group A whose mother was group O marries a woman of "
        "blood group B whose father was group O. List the blood groups their "
        "children could have, and find the probability that a child is group O."
    ),
    steps=[
        "Blood group is controlled by three alleles of one gene: I^A, I^B and "
        "I^O. I^A and I^B are codominant with each other, and both are "
        "dominant to I^O.",
        "The man is group A, and his mother was group O, so she was I^O I^O "
        "and could only give him I^O. He is therefore I^A I^O.",
        "The woman is group B, and her father was group O, so by the same "
        "argument she is I^B I^O.",
        "Cross I^A I^O × I^B I^O. The man's gametes carry I^A or I^O; the "
        "woman's carry I^B or I^O.",
        "The four equally likely combinations are I^A I^B (group AB), "
        "I^A I^O (group A), I^B I^O (group B) and I^O I^O (group O).",
        f"So all four groups are possible, each with probability 1/4 = "
        f"{n(bg_each)}%.",
        f"In particular the probability of a group O child is 1/4 = "
        f"{n(bg_each)}%.",
        "Group AB appears because I^A and I^B are codominant: both antigens "
        "are made, and neither hides the other.",
    ],
    answer=(
        f"AB, A, B or O, each with probability 1/4; group O is {n(bg_each)}%"
    ),
))

# ------------------------------------------ 9. energy lost between trophic levels
producer_kj, herbivore_kj = 20000.0, 2000.0
energy_lost = producer_kj - herbivore_kj
percent_lost = energy_lost / producer_kj * 100
percent_passed = herbivore_kj / producer_kj * 100
EXAMPLES.append(doc(
    num=9, slug="energy-lost-between-levels",
    title="Energy lost between producers and primary consumers",
    topic="Food chains and energy flow", subtopic="Energy loss",
    section="G2", numeric=True,
    question=(
        f"In a grassland the producers fix {n(producer_kj)} kJ of energy per "
        f"square metre per year. The primary consumers that feed on them gain "
        f"{n(herbivore_kj)} kJ per square metre per year. Find (a) the energy "
        "lost between the two levels, (b) that loss as a percentage, and state "
        "two ways the energy is lost."
    ),
    steps=[
        "Part (a). Energy lost = energy at the lower level − energy passed to "
        "the level above.",
        f"Energy lost = {n(producer_kj)} − {n(herbivore_kj)} = "
        f"{n(energy_lost)} kJ per square metre per year.",
        "Part (b). Percentage lost = energy lost ÷ energy available × 100.",
        f"Percentage lost = {n(energy_lost)} ÷ {n(producer_kj)} × 100 = "
        f"{n(percent_lost)}%.",
        f"Checking: the energy passed on is {n(herbivore_kj)} ÷ "
        f"{n(producer_kj)} × 100 = {n(percent_passed)}%, and "
        f"{n(percent_lost)}% + {n(percent_passed)}% = 100%.",
        "The energy is lost mainly as heat from respiration, in undigested "
        "material passed out in faeces, and in nitrogenous waste such as urine. "
        "Some plant material is also never eaten at all.",
        "Because so much is lost at each step, a food chain rarely has more "
        "than four or five links.",
    ],
    answer=(
        f"(a) {n(energy_lost)} kJ per square metre per year  "
        f"(b) {n(percent_lost)}%, lost mainly as heat from respiration and in "
        "faeces and urine"
    ),
))

# --------------------------------------------- 10. percentage energy transferred
prod_kj, prim_kj, sec_kj = 20000.0, 2000.0, 150.0
first_transfer = prim_kj / prod_kj * 100
second_transfer = sec_kj / prim_kj * 100
overall_transfer = sec_kj / prod_kj * 100
EXAMPLES.append(doc(
    num=10, slug="percentage-energy-transferred",
    title="Percentage of energy transferred along a food chain",
    topic="Food chains and energy flow", subtopic="Efficiency of transfer",
    section="G2", numeric=True,
    question=(
        f"Along the food chain grass → grasshopper → lizard, the energy "
        f"measured at each level per square metre per year is: grass "
        f"{n(prod_kj)} kJ, grasshoppers {n(prim_kj)} kJ, lizards "
        f"{n(sec_kj)} kJ. Find the percentage of energy transferred (a) from "
        "grass to grasshoppers, (b) from grasshoppers to lizards, (c) from "
        "grass to lizards overall."
    ),
    steps=[
        "Percentage transferred = energy at the higher level ÷ energy at the "
        "level below × 100.",
        f"Part (a). {n(prim_kj)} ÷ {n(prod_kj)} × 100 = {n(first_transfer)}%.",
        f"Part (b). {n(sec_kj)} ÷ {n(prim_kj)} × 100 = {n(second_transfer)}%.",
        f"Part (c). Overall, {n(sec_kj)} ÷ {n(prod_kj)} × 100 = "
        f"{n(overall_transfer)}%.",
        f"Check that (c) agrees with (a) and (b) combined: "
        f"{n(first_transfer)}% of {n(second_transfer)}% is "
        f"{n(first_transfer/100 * second_transfer)}%, which matches.",
        "This is why a pyramid of energy always narrows upwards, and it never "
        "inverts: each level can only hold what the level below passed on.",
    ],
    answer=(
        f"(a) {n(first_transfer)}%  (b) {n(second_transfer)}%  "
        f"(c) {n(overall_transfer)}%"
    ),
))

# ------------------------------------------------- 11. potometer transpiration
bubble_mm, bubble_min, bore_area = 45.0, 3.0, 0.5
rate_mm_per_min = bubble_mm / bubble_min
rate_vol_per_min = rate_mm_per_min * bore_area
rate_vol_per_hour = rate_vol_per_min * 60
EXAMPLES.append(doc(
    num=11, slug="potometer-rate",
    title="Rate of transpiration measured with a potometer",
    topic="Transport in plants", subtopic="Transpiration",
    section="C1", numeric=True,
    question=(
        f"In a potometer the air bubble moves {n(bubble_mm)} mm along the "
        f"capillary tube in {n(bubble_min)} minutes. The tube has a uniform "
        f"bore of cross-sectional area {n(bore_area)} mm². Find the rate of "
        "water uptake (a) in mm per minute, (b) in mm³ per minute, (c) in mm³ "
        "per hour."
    ),
    steps=[
        "Part (a). Rate = distance moved ÷ time taken.",
        f"Rate = {n(bubble_mm)} ÷ {n(bubble_min)} = {n(rate_mm_per_min)} mm "
        "per minute.",
        "Part (b). The water drawn in fills a cylinder of that length, so "
        "volume = length × cross-sectional area.",
        f"Rate = {n(rate_mm_per_min)} × {n(bore_area)} = "
        f"{n(rate_vol_per_min)} mm³ per minute.",
        "Part (c). There are 60 minutes in an hour.",
        f"Rate = {n(rate_vol_per_min)} × 60 = {n(rate_vol_per_hour)} mm³ per "
        "hour.",
        "Strictly the potometer measures water uptake, not transpiration. "
        "The two are taken as equal only because the small amount of water "
        "kept back for photosynthesis and for keeping cells turgid is "
        "negligible in comparison.",
    ],
    answer=(
        f"(a) {n(rate_mm_per_min)} mm per minute  (b) {n(rate_vol_per_min)} "
        f"mm³ per minute  (c) {n(rate_vol_per_hour)} mm³ per hour"
    ),
))

# ------------------------------------------------------ 12. capture-recapture
first_catch, second_catch, marked_again = 60.0, 80.0, 15.0
population = first_catch * second_catch / marked_again
EXAMPLES.append(doc(
    num=12, slug="capture-recapture",
    title="Estimating a population by capture and recapture",
    topic="Ecology and ecosystems", subtopic="Estimating population size",
    section="G1", numeric=True,
    question=(
        f"A student catches {n(first_catch)} grasshoppers in a field, marks "
        "them harmlessly and releases them. Some days later she catches "
        f"{n(second_catch)} grasshoppers, of which {n(marked_again)} carry the "
        "mark. Estimate the number of grasshoppers in the field."
    ),
    steps=[
        "The method assumes the marked animals have mixed evenly back into the "
        "population, so the fraction marked in the second sample is the "
        "fraction marked in the whole population.",
        "That gives the Lincoln index: population = (number in first sample × "
        "number in second sample) ÷ number marked in the second sample.",
        f"Population = ({n(first_catch)} × {n(second_catch)}) ÷ "
        f"{n(marked_again)}.",
        f"Population = {n(first_catch*second_catch)} ÷ {n(marked_again)} = "
        f"{n(population)}.",
        "The estimate assumes no births, deaths or migration between the two "
        "catches, that the mark does not rub off or make the animal easier for "
        "a predator to see, and that marked animals are no more or less likely "
        "to be caught again. If any of these fails, the estimate is wrong.",
    ],
    answer=f"about {n(population)} grasshoppers",
))

# --------------------------------------------------- 13. breathing rate change
rest_rate, exercise_rate = 16.0, 28.0
rate_increase = exercise_rate - rest_rate
percent_increase = rate_increase / rest_rate * 100
EXAMPLES.append(doc(
    num=13, slug="breathing-rate-change",
    title="Change in breathing rate after exercise",
    topic="Respiration", subtopic="Breathing and gaseous exchange",
    section="C3", numeric=True,
    question=(
        f"A student's breathing rate at rest is {n(rest_rate)} breaths per "
        f"minute. Immediately after running it is {n(exercise_rate)} breaths "
        "per minute. Find (a) the increase in breathing rate, (b) the "
        "percentage increase, and explain the change."
    ),
    steps=[
        "Part (a). Increase = rate after exercise − rate at rest.",
        f"Increase = {n(exercise_rate)} − {n(rest_rate)} = {n(rate_increase)} "
        "breaths per minute.",
        "Part (b). Percentage increase = increase ÷ original rate × 100.",
        f"Percentage increase = {n(rate_increase)} ÷ {n(rest_rate)} × 100 = "
        f"{n(percent_increase)}%.",
        "Explanation: exercising muscles respire faster, using more oxygen and "
        "producing more carbon dioxide.",
        "The rise in carbon dioxide in the blood is detected, and the "
        "breathing centre in the medulla oblongata makes the breathing faster "
        "and deeper. This clears the extra carbon dioxide and supplies the "
        "extra oxygen.",
        "If the muscles still cannot get enough oxygen they respire "
        "anaerobically, producing lactic acid and building an oxygen debt, "
        "which is why breathing stays fast for a while after the run ends.",
    ],
    answer=(
        f"(a) {n(rate_increase)} breaths per minute  (b) {n(percent_increase)}%"
    ),
))

# ------------------------------------------- 14. oxygen from alveolus to cell
EXAMPLES.append(doc(
    num=14, slug="oxygen-alveolus-to-cell",
    title="The path of oxygen from an alveolus to a respiring muscle cell",
    topic="Transport in animals", subtopic="Gaseous exchange and transport",
    section="C2", numeric=False,
    question=(
        "Describe the path taken by a molecule of oxygen from the air inside "
        "an alveolus to a respiring muscle cell in the leg."
    ),
    steps=[
        "Start at the exchange surface. Air in the alveolus is richer in "
        "oxygen than the blood arriving in the capillary around it, so oxygen "
        "diffuses down that concentration gradient.",
        "It crosses the moist, very thin wall of the alveolus and the equally "
        "thin capillary wall, dissolving in the film of moisture first. Both "
        "walls are one cell thick, so the distance is short.",
        "In the capillary the oxygen enters a red blood cell and combines with "
        "haemoglobin to form oxyhaemoglobin. This keeps the amount dissolved "
        "in the plasma low, so the gradient into the blood is maintained.",
        "The blood, now oxygenated, is carried in the pulmonary vein to the "
        "left atrium of the heart, passes into the left ventricle, and is "
        "pumped out into the aorta.",
        "Arteries branch from the aorta and carry the blood towards the leg, "
        "dividing into arterioles and then into capillaries that run between "
        "the muscle cells.",
        "The muscle cells are respiring, so their oxygen concentration is low "
        "and their carbon dioxide concentration high. Oxyhaemoglobin is "
        "unstable in such conditions and breaks down, releasing oxygen.",
        "The oxygen diffuses out of the capillary, through the tissue fluid "
        "and across the cell membrane into the muscle cell, and finally into a "
        "mitochondrion, where it is used in aerobic respiration to release "
        "energy.",
        "Every step is diffusion down a concentration gradient. Nothing pushes "
        "the oxygen across a membrane; the gradient is what moves it, and the "
        "circulation is what keeps the gradient steep.",
    ],
    answer=(
        "oxygen diffuses from the alveolus across the alveolar and capillary "
        "walls into the blood, is carried as oxyhaemoglobin in red blood cells "
        "through the pulmonary vein, heart and aorta to the muscle capillaries, "
        "then dissociates and diffuses into the muscle cell and its "
        "mitochondria, moving down a concentration gradient at every stage"
    ),
))

# ----------------------------------------------------- 15. artery versus vein
EXAMPLES.append(doc(
    num=15, slug="artery-and-vein",
    title="Comparing an artery with a vein",
    topic="Transport in animals", subtopic="Blood vessels",
    section="C2", numeric=False,
    question=(
        "Compare the structure of an artery with that of a vein, and relate "
        "each difference to the work the vessel does."
    ),
    steps=[
        "Begin with the job each vessel does. An artery carries blood away "
        "from the heart, and a vein carries blood back towards it.",
        "Pressure. Blood leaves the heart in surges at high pressure, so an "
        "artery must withstand and smooth those surges. By the time blood has "
        "passed through the capillaries the pressure is low and steady, so a "
        "vein does not.",
        "Wall. The artery has a thick wall with much elastic tissue and smooth "
        "muscle. It stretches as a surge arrives and recoils afterwards, "
        "keeping the blood moving between beats. The vein has a much thinner "
        "wall with far less muscle and elastic tissue.",
        "Lumen. The artery has a relatively narrow lumen, which helps keep the "
        "pressure up. The vein has a wide lumen, which lowers the resistance "
        "to a slow, low-pressure flow.",
        "Valves. A vein has pocket-shaped semilunar valves along its length, "
        "because the low pressure would otherwise let blood fall backwards. "
        "Contraction of the surrounding skeletal muscles squeezes the vein, "
        "and the valves make sure the blood squeezed along can only go towards "
        "the heart. An artery needs no such valves, except the ones guarding "
        "its exit from the heart.",
        "Contents. Arteries usually carry oxygenated blood and veins "
        "deoxygenated blood, but this is about what they happen to carry, not "
        "about what they are. The pulmonary artery carries deoxygenated blood "
        "to the lungs and the pulmonary vein carries oxygenated blood back, so "
        "define the vessels by their direction of flow, not by their contents.",
    ],
    answer=(
        "an artery carries blood away from the heart at high pressure and has "
        "a thick elastic muscular wall, a narrow lumen and no valves along its "
        "length; a vein returns blood to the heart at low pressure and has a "
        "thin wall, a wide lumen and semilunar valves; direction of flow, not "
        "the oxygenation of the blood, is what distinguishes them"
    ),
))

# ------------------------------------------------------------ 16. reflex arc
EXAMPLES.append(doc(
    num=16, slug="reflex-arc",
    title="The pathway of a reflex action",
    topic="Coordination", subtopic="The nervous system",
    section="D2", numeric=False,
    question=(
        "A person treads on a sharp stone and the foot is lifted at once. "
        "Describe the pathway of the nerve impulse, and explain why the action "
        "happens before the person feels the pain."
    ),
    steps=[
        "Stimulus. The sharp stone presses on the skin of the foot.",
        "Receptor. Pain receptors in the skin detect the stimulus and start a "
        "nerve impulse.",
        "Sensory neurone. The impulse travels along a sensory neurone, whose "
        "cell body lies in a ganglion on the dorsal root, into the grey matter "
        "of the spinal cord.",
        "Synapse and relay neurone. The impulse is passed across a synapse to "
        "a relay neurone inside the spinal cord. At a synapse a transmitter "
        "substance is released into the gap, crosses it and starts a new "
        "impulse in the next neurone, which is why an impulse can travel only "
        "one way.",
        "Motor neurone. A second synapse passes the impulse to a motor neurone "
        "that leaves the cord by the ventral root.",
        "Effector and response. The motor neurone carries the impulse to the "
        "flexor muscle of the leg, the effector, which contracts and lifts the "
        "foot away from the stone.",
        "Why it precedes the pain: the whole pathway is completed within the "
        "spinal cord, so the response is made without waiting for the brain. "
        "A separate impulse travels up the cord to the brain, and it is only "
        "when it arrives there that the person becomes aware of the pain — by "
        "which time the foot has already moved.",
        "A reflex action is therefore rapid, automatic and not learned, and "
        "its survival value is that it protects the body from damage faster "
        "than a considered decision could.",
    ],
    answer=(
        "stimulus → pain receptor in the skin → sensory neurone → spinal cord, "
        "where a relay neurone links it across two synapses → motor neurone → "
        "leg muscle, which contracts and lifts the foot; the arc is completed "
        "in the spinal cord without the brain, and awareness of pain comes "
        "only when a separate impulse reaches the brain afterwards"
    ),
))

# ------------------------------------------------------- 17. wilting and water
EXAMPLES.append(doc(
    num=17, slug="wilting-and-recovery",
    title="Why a wilted plant becomes firm again after watering",
    topic="The cell and its environment", subtopic="Osmosis and turgor",
    section="A1", numeric=False,
    question=(
        "A potted plant left unwatered on a hot afternoon droops. After "
        "watering it becomes firm again by the next morning. Explain both "
        "observations in terms of osmosis."
    ),
    steps=[
        "A plant cell has a cell sap in its vacuole that is a fairly "
        "concentrated solution, and a cell membrane that is partially "
        "permeable: it lets water through but holds back dissolved sugars and "
        "salts.",
        "Why it drooped. On a hot afternoon the plant transpires quickly, and "
        "with dry soil it cannot replace the water lost.",
        "Water passes out of the cells, the vacuoles shrink, and the "
        "protoplasm stops pressing the cell wall outwards. The cells become "
        "flaccid, and if water loss continues the protoplasm pulls away from "
        "the wall, which is plasmolysis.",
        "Herbaceous stems and leaves are held up mainly by the turgor of their "
        "cells, so once the cells go flaccid the plant loses its support and "
        "droops. Wilting also closes the stomata, which slows further loss.",
        "Why it recovered. The watered soil now holds a more dilute solution "
        "than the cell sap of the root hair cells.",
        "Water therefore moves into the root hair cells by osmosis, down the "
        "water potential gradient across the partially permeable membrane, and "
        "passes on from cell to cell and up the xylem to the leaves.",
        "As the vacuoles refill, the protoplasm presses outwards on the cell "
        "wall again. The wall is strong and resists, so the cell becomes "
        "turgid and the pressure restores the plant's firmness.",
        "The cell does not burst, because the rigid cellulose wall exerts an "
        "inward pressure that stops water entering once the cell is fully "
        "turgid. An animal cell, having no such wall, would burst in pure "
        "water.",
    ],
    answer=(
        "the plant drooped because water lost in transpiration was not "
        "replaced, so its cells became flaccid and lost the turgor that "
        "supports the stem and leaves; after watering the soil solution is "
        "more dilute than the cell sap, so water enters the root hair cells by "
        "osmosis and passes up to the leaves, the vacuoles refill and the "
        "cells become turgid again"
    ),
))

# ------------------------------------------------------------ 18. germination
EXAMPLES.append(doc(
    num=18, slug="seed-germination",
    title="What happens when a bean seed germinates",
    topic="Growth and development", subtopic="Germination",
    section="E3", numeric=False,
    question=(
        "Describe what happens inside a bean seed when it germinates, and "
        "state the external conditions needed."
    ),
    steps=[
        "Conditions. A viable seed needs water, a suitable warmth and oxygen. "
        "Light is not needed for germination itself, and many seeds germinate "
        "underground in the dark.",
        "Imbibition. The seed takes in water through the micropyle and the "
        "testa. It swells, and the testa softens and splits.",
        "Enzymes activated. The water lets the enzymes in the seed work again. "
        "Amylase breaks the stored starch in the cotyledons down to maltose "
        "and then to glucose; proteases break stored protein down to amino "
        "acids; lipases break fats down to fatty acids and glycerol.",
        "Why that matters. Starch is insoluble and cannot be moved. Once it is "
        "digested to sugar it is soluble and can be transported to the embryo.",
        "Respiration. Some of the glucose is respired, using the oxygen the "
        "seed takes in, to release the energy the growing embryo needs. This "
        "is why a germinating seed gets warm and why waterlogged soil, which "
        "excludes air, prevents germination.",
        "Growth of the embryo. The rest of the soluble food is used to build "
        "new cells. The radicle emerges first and grows downwards, anchoring "
        "the seedling and taking in water. The plumule follows and grows "
        "upwards towards the light.",
        "The bean is epigeal: the hypocotyl lengthens and pulls the cotyledons "
        "above the soil, where they turn green and photosynthesise for a while "
        "before shrivelling. In a hypogeal seed such as maize the cotyledon "
        "stays below the ground instead.",
        "The seedling depends on the food stored in the cotyledons until its "
        "first true leaves open and it can make its own food. Its dry mass "
        "actually falls during this stage, because stored food is being "
        "respired away faster than anything new is being made.",
    ],
    answer=(
        "given water, warmth and oxygen the seed imbibes water and swells, its "
        "testa splits, enzymes such as amylase digest the insoluble stored "
        "food in the cotyledons into soluble sugars and amino acids, some is "
        "respired for energy and the rest builds new cells; the radicle "
        "emerges first and grows down, then the plumule grows up, and in the "
        "epigeal bean the cotyledons are carried above the soil until the "
        "first foliage leaves can photosynthesise"
    ),
))


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, text in EXAMPLES:
        (ROOT / name).write_text(text, encoding="utf-8")
    print(
        f"wrote {len(EXAMPLES)} worked examples to {ROOT} "
        f"({len(NUMERIC)} numeric, {len(EXPLANATORY)} explanatory)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
