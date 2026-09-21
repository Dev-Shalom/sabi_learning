"""Every practice template's answer, recomputed by something that did not write it.

`sabi/practice/maths.py` and `sabi/practice/physics.py` compute their answers
rather than stating them, which removes one class of mistake and not the
other: a formula applied to the wrong quantity gives an answer that is
arithmetically consistent with itself and still wrong to hand a student.

So this file does the mathematics and the physics again, from the outside. It
reads the *question text the student is shown*, parses the numbers back out of
it, and computes the answer with plain floats and explicit formulae. It shares
no arithmetic with the generator: nothing here imports `Fraction`-based
helpers from `sabi.practice`, nothing calls `templates.n`, and nothing uses
`sabi.valuematch` to decide whether two numbers agree.

Working from the question rather than from `params` is deliberate. A checker
fed `params` can recompute the generator's intended quantity perfectly while
the sentence on the screen asks for something else, and that check passes
while the student is misled. Parsing the sentence is the only way to notice.

Modelled on `tests/test_physics_corpus.py`, including the coverage test that
fails when a template arrives without a check.

Nothing here needs Postgres -- it is pure computation over the registry -- so
the two database fixtures in `conftest.py` are overridden below.
"""

from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path
from typing import Any, Callable, NamedTuple

import pytest

from sabi.corpus.loader import CorpusError, load_file
from sabi.practice import templates as T

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"

# A constraint that holds for seed 0 and breaks for seed 37 is the thing worth
# catching, so every template is run over a spread of seeds rather than one.
SEEDS = range(60)

# WAEC's pi, and WAEC's g. Written out here rather than imported, because a
# constant imported from the module under test is a constant nobody checked.
PI = 22 / 7
G = 10.0

# The longest answer a student should have to type into a phone keyboard.
MAX_ANSWER_LENGTH = 24

LIVE_SUBJECTS = {"Mathematics", "Physics", "Chemistry"}
LIVE_BOARD = "WAEC"


# --------------------------------------------------------------- no database


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    """Override conftest's schema bootstrap and corpus ingest.

    This module computes; it does not query. Overriding by name keeps the
    autouse fixture from dragging a Postgres round trip into a pure-arithmetic
    suite.
    """
    return None


@pytest.fixture(autouse=True)
def clean_traffic():
    """Override conftest's per-test TRUNCATE. Nothing here writes rows."""
    yield


# ------------------------------------------------------------------ plumbing


class Rounded(NamedTuple):
    """An answer the question explicitly asked to be rounded."""

    value: float
    places: int


class Unordered(NamedTuple):
    """A set of numbers, where the order they are typed in does not matter."""

    values: frozenset


def number(text: str) -> float:
    """Read back a number the way a student's answer would be read.

    Handles the fraction form the four fraction-answer templates use. This is
    deliberately not `sabi.valuematch`: deciding that "1/3" and 0.333... are
    the same value is this file's job, not the marker's.
    """
    text = text.strip()
    if "/" in text:
        top, _, bottom = text.partition("/")
        return float(top) / float(bottom)
    return float(text)


def decimal_places(text: str) -> int:
    text = text.strip()
    if "/" in text or "." not in text:
        return 0
    return len(text.split(".", 1)[1])


def grab(pattern: str, question: str) -> tuple[str, ...]:
    """Pull the numbers back out of the sentence the student reads."""
    found = re.search(pattern, question)
    assert found is not None, (
        f"the question does not read as expected -- {pattern!r} does not "
        f"match {question!r}"
    )
    return found.groups()


def ints(pattern: str, question: str) -> tuple[int, ...]:
    return tuple(int(g) for g in grab(pattern, question))


def floats(pattern: str, question: str) -> tuple[float, ...]:
    return tuple(float(g) for g in grab(pattern, question))


def polynomial(text: str) -> dict[int, int]:
    """Read '2x^3 - 5x^2 + x - 4' as {3: 2, 2: -5, 1: 1, 0: -4}.

    Written once and used for the quadratics and the cubic, so the checks on
    those templates start from the printed expression rather than from the
    coefficients the generator happened to store.
    """
    squashed = text.replace(" ", "")
    assert squashed, "empty expression"
    out: dict[int, int] = {}
    for token in re.findall(r"[+-]?[^+-]+", squashed):
        sign = -1 if token.startswith("-") else 1
        body = token.lstrip("+-")
        if "x" in body:
            magnitude, _, tail = body.partition("x")
            power = int(tail[1:]) if tail.startswith("^") else 1
            size = int(magnitude) if magnitude else 1
        else:
            power, size = 0, int(body)
        out[power] = out.get(power, 0) + sign * size
    return out


# ------------------------------------------------------------- the checkers
#
# One per template. Each is handed the stored params and the rendered
# question, and returns the answer it believes the question has. The formulae
# are written out in full, in floats, with names chosen here -- so a slip
# copied from the generator would have to be made twice, identically, to go
# unnoticed.


def check_base_to_ten(params, question):
    shown, base = grab(r"Convert (\d+) from base (\d+) to base ten", question)
    base = int(base)
    for figure in shown:
        assert int(figure) < base, f"digit {figure} is not valid in base {base}"
    assert shown[0] != "0", "a converted numeral should not have a leading zero"
    places = len(shown)
    return float(sum(int(f) * base ** (places - 1 - i) for i, f in enumerate(shown)))


def check_standard_form_product(params, question):
    a, p, b, q = ints(
        r"\((\d+) x 10\^(-?\d+)\) x \((\d+) x 10\^(-?\d+)\)", question
    )
    return a * b * (10.0 ** (p + q))


def check_percentage_error(params, question):
    true_value, measured = floats(
        r"true value is ([\d.]+) cm is measured as ([\d.]+) cm", question
    )
    return abs(measured - true_value) / true_value * 100.0


def check_index_equation(params, question):
    # A zero offset is not printed at all, so the sign and the number are
    # one optional group rather than two required ones.
    base, coefficient, sign, offset, right = grab(
        r"Solve for x: (\d+)\^\((\d+)x(?: ([+-]) (\d+))?\) = (\d+)", question
    )
    base, coefficient, right = int(base), int(coefficient), int(right)
    offset = 0 if offset is None else int(offset) * (1 if sign == "+" else -1)
    # What power of the base is the right-hand side? Found by logarithm, not
    # by repeating the generator's construction.
    power = round(math.log(right) / math.log(base))
    assert base**power == right, f"{right} is not a power of {base}"
    exponent = power - offset
    assert exponent % coefficient == 0, "x would not come out whole"
    return float(exponent // coefficient)


def check_fractional_index(params, question):
    base, power, root = ints(r"Evaluate (\d+)\^\((\d+)/(\d+)\)", question)
    return float(base) ** (power / root)


def check_logarithm_from_given(params, question):
    (value,) = ints(r"evaluate log (\d+)", question)
    # Factor the number myself, then use the two table values the question
    # states. The true log10 differs in the fourth place, which is the point.
    twos = threes = 0
    left = value
    while left % 2 == 0:
        left //= 2
        twos += 1
    while left % 3 == 0:
        left //= 3
        threes += 1
    assert left == 1, f"log {value} cannot be found from log 2 and log 3 alone"
    return round(twos * 0.3010 + threes * 0.4771, 4)


def check_logarithmic_equation(params, question):
    base, power = ints(r"log base (\d+) of x = (\d+)", question)
    return float(base) ** power


def check_two_set_venn(params, question):
    total, maths, physics = ints(
        r"In a class of (\d+) students, (\d+) offer Mathematics and (\d+) "
        r"offer Physics",
        question,
    )
    both = maths + physics - total
    assert both >= 0, "inclusion-exclusion gives a negative overlap"
    assert maths <= total and physics <= total, "a subject outnumbers the class"
    return float(both)


def check_simplify_surd(params, question):
    value, inside = ints(
        r"square root of (\d+) in the form a root (\d+)", question
    )
    assert value % inside == 0, f"{inside} does not divide {value}"
    outside = math.isqrt(value // inside)
    assert outside * outside * inside == value, "the surd does not simplify exactly"
    return float(outside)


def check_arithmetic_progression(params, question):
    m, term_m, p, term_p, count = ints(
        r"The (\d+)\w\w term of an arithmetic progression is (-?\d+) and the "
        r"(\d+)\w\w term is (-?\d+)\. Find the sum of the first (\d+) terms",
        question,
    )
    difference = (term_p - term_m) / (p - m)
    first = term_m - (m - 1) * difference
    return count / 2.0 * (2.0 * first + (count - 1) * difference)


def check_geometric_progression(params, question):
    first, ratio, which = ints(
        r"geometric progression is (\d+) and the common ratio is (\d+)\. Find "
        r"the (\d+)\w\w term",
        question,
    )
    return float(first) * float(ratio) ** (which - 1)


def check_sum_to_infinity(params, question):
    first, denominator = ints(
        r"geometric progression is (\d+) and the common ratio is 1/(\d+)\. "
        r"Find the sum to infinity",
        question,
    )
    ratio = 1.0 / denominator
    assert abs(ratio) < 1, "the series does not converge"
    return first / (1.0 - ratio)


def check_matrix_determinant(params, question):
    top_left, top_right, bottom_left, bottom_right = ints(
        r"first row \((-?\d+), (-?\d+)\) and second row \((-?\d+), (-?\d+)\)",
        question,
    )
    return float(top_left * bottom_right - top_right * bottom_left)


def check_simple_interest_principal(params, question):
    interest, years, rate = floats(
        r"simple interest of ([\d.]+) naira in ([\d.]+) years at ([\d.]+) per "
        r"cent per annum",
        question,
    )
    return 100.0 * interest / (rate * years)


def check_compound_interest_amount(params, question):
    principal, rate, years = floats(
        r"([\d.]+) naira is invested at ([\d.]+) per cent per annum compound "
        r"interest\. Find the amount after ([\d.]+) years",
        question,
    )
    return principal * (1.0 + rate / 100.0) ** years


def check_hire_purchase_extra(params, question):
    cash, deposit, months, instalment = floats(
        r"costs ([\d.]+) naira cash\. On hire purchase a buyer pays a deposit "
        r"of ([\d.]+) naira and ([\d.]+) monthly instalments of ([\d.]+) naira",
        question,
    )
    hire_purchase = deposit + months * instalment
    assert hire_purchase > cash, (
        "hire purchase comes out cheaper than cash, which is not a question "
        "anybody should practise on"
    )
    return hire_purchase - cash


def check_joint_variation(params, question):
    x1, y1, z1, x2, y2 = floats(
        r"When x = ([\d.]+) and y = ([\d.]+), z = ([\d.]+)\. Find z when "
        r"x = ([\d.]+) and y = ([\d.]+)",
        question,
    )
    constant = z1 / (x1 * y1 * y1)
    return constant * x2 * y2 * y2


def check_factorise_trinomial_roots(params, question):
    (expression,) = grab(r"Factorise (.+?) and hence", question)
    return _roots_of(expression)


def check_quadratic_roots(params, question):
    (expression,) = grab(r"Solve the equation (.+?) = 0\.", question)
    return _roots_of(expression)


def _roots_of(expression: str) -> Unordered:
    """Solve the printed quadratic with the formula, and check by substitution."""
    terms = polynomial(expression)
    a = terms.get(2, 0)
    b = terms.get(1, 0)
    c = terms.get(0, 0)
    assert a != 0, f"{expression!r} is not a quadratic"
    discriminant = b * b - 4 * a * c
    assert discriminant > 0, f"{expression!r} has no two distinct real roots"
    surd = math.sqrt(discriminant)
    first = (-b + surd) / (2 * a)
    second = (-b - surd) / (2 * a)
    for root in (first, second):
        residue = a * root * root + b * root + c
        assert abs(residue) < 1e-6, f"{root} does not satisfy {expression!r}"
    return Unordered(frozenset({first, second}))


def check_simultaneous_linear(params, question):
    # A coefficient of one is printed as `x`, not `1x`, so each coefficient
    # is an optional run of digits that defaults to 1.
    a1, b1, c1, a2, b2, c2 = grab(
        r"equations (-?\d*)x \+ (\d*)y = (-?\d+) and "
        r"(-?\d*)x - (\d*)y = (-?\d+)",
        question,
    )

    def size(text, default=1):
        if text in ("", "+"):
            return default
        if text == "-":
            return -default
        return int(text)

    a1, b1, c1 = size(a1), size(b1), int(c1)
    a2, b2, c2 = size(a2), size(b2), int(c2)
    # The second equation is printed with a minus sign, so its y coefficient
    # is the negative of what is shown.
    b2 = -b2
    determinant = a1 * b2 - a2 * b1
    assert determinant != 0, "the two equations do not meet in a single point"
    x = (c1 * b2 - c2 * b1) / determinant
    y = (a1 * c2 - a2 * c1) / determinant
    # Both equations, checked by substitution, so a sign slip in either the
    # printing or the solving shows up here.
    assert abs(a1 * x + b1 * y - c1) < 1e-9
    assert abs(a2 * x + b2 * y - c2) < 1e-9
    return x


def check_change_of_subject(params, question):
    v_squared, u, s = floats(
        r"v\^2 = ([\d.]+), u = ([\d.]+) and s = ([\d.]+)", question
    )
    return (v_squared - u * u) / (2.0 * s)


def check_sum_and_product_of_roots(params, question):
    expression, wanted = grab(
        r"The roots of (.+?) = 0 are alpha and beta\. Find the (sum|product) "
        r"of the roots",
        question,
    )
    terms = polynomial(expression)
    a = terms.get(2, 0)
    b = terms.get(1, 0)
    c = terms.get(0, 0)
    assert a != 0, f"{expression!r} is not a quadratic"
    return (-b / a) if wanted == "sum" else (c / a)


def check_polygon_interior_sum(params, question):
    (sides,) = ints(r"polygon with (\d+) sides", question)
    assert sides >= 3, "fewer than three sides is not a polygon"
    return (sides - 2) * 180.0


def check_polygon_from_exterior(params, question):
    (exterior,) = ints(
        r"exterior angle of a regular polygon is (\d+) degrees", question
    )
    assert 360 % exterior == 0, f"{exterior} degrees describes no regular polygon"
    return 360.0 / exterior


def check_angle_at_centre(params, question):
    (at_circumference,) = ints(
        r"circumference of a circle by an arc is (\d+) degrees", question
    )
    return 2.0 * at_circumference


def check_cyclic_quadrilateral(params, question):
    (given,) = ints(r"angle PQR is (\d+) degrees", question)
    assert 0 < given < 180, "an angle of a cyclic quadrilateral is between 0 and 180"
    return 180.0 - given


def check_sector_area(params, question):
    radius, angle = ints(
        r"radius (\d+) cm subtends an angle of (\d+) degrees", question
    )
    assert 0 < angle < 360, "a sector angle should be a proper part of a turn"
    return angle / 360.0 * PI * radius * radius


def check_cone_volume(params, question):
    radius, height = ints(r"base radius (\d+) cm and height (\d+) cm", question)
    return PI * radius * radius * height / 3.0


def check_sphere_surface_area(params, question):
    (radius,) = ints(r"sphere of radius (\d+) cm", question)
    return 4.0 * PI * radius * radius


def check_cosine_rule_side(params, question):
    b, c, angle = floats(
        r"b = ([\d.]+) cm, c = ([\d.]+) cm and angle A = ([\d.]+) degrees",
        question,
    )
    # Straight from the trig function, not from a stored exact cosine.
    squared = b * b + c * c - 2.0 * b * c * math.cos(math.radians(angle))
    assert squared > 0, "the triangle does not close"
    return Rounded(math.sqrt(squared), 1)


def check_angle_of_elevation_height(params, question):
    distance, angle = floats(
        r"a point ([\d.]+) m from the foot of a vertical tower, the angle of "
        r"elevation of the top of the tower is ([\d.]+) degrees",
        question,
    )
    radians = math.radians(angle)
    # sin/cos rather than tan, so the two computations do not share a call.
    return Rounded(distance * math.sin(radians) / math.cos(radians), 1)


def check_gradient_at_a_point(params, question):
    curve, at = grab(
        r"Given that y = (.+?), find dy/dx and hence the gradient of the curve "
        r"at x = (-?\d+)",
        question,
    )
    terms = polynomial(curve)
    at = float(at)

    def y(x: float) -> float:
        return sum(coefficient * x**power for power, coefficient in terms.items())

    # Differentiate numerically. For a cubic the central difference is exact
    # to within (leading coefficient) x h^2, which at h = 1e-4 is far inside
    # the half a unit that separates one whole-number gradient from the next.
    h = 1e-4
    slope = (y(at + h) - y(at - h)) / (2 * h)
    return float(round(slope))


def check_definite_integral(params, question):
    integrand, lower, upper = grab(
        r"integral of (.+?) with respect to x, from x = (-?\d+) to x = (-?\d+)",
        question,
    )
    terms = polynomial(integrand)
    lower, upper = float(lower), float(upper)
    assert upper > lower, "the limits are the wrong way round"
    # Term by term, as a single expression rather than an antiderivative
    # evaluated twice.
    return sum(
        coefficient * (upper ** (power + 1) - lower ** (power + 1)) / (power + 1)
        for power, coefficient in terms.items()
    )


def check_grouped_mean(params, question):
    (table,) = grab(r"group of students \(([^)]*)\)", question)
    classes = []
    for entry in table.split(";"):
        bounds, _, count = entry.partition(":")
        low, _, high = bounds.strip().partition("-")
        classes.append((float(low), float(high), float(count)))
    assert len(classes) >= 2, "a grouped mean needs more than one class"
    for (_, high, _), (low, _, _) in zip(classes, classes[1:]):
        assert low > high, f"classes {high} and {low} overlap"
    students = sum(count for _, _, count in classes)
    assert students > 0, "no students in the table"
    total = sum((low + high) / 2.0 * count for low, high, count in classes)
    return Rounded(total / students, 2)


def check_probability_without_replacement(params, question):
    red, blue = floats(
        r"contains ([\d.]+) red balls and ([\d.]+) blue balls", question
    )
    drawn = red + blue
    assert red >= 2, "two red balls cannot be drawn"
    return (red / drawn) * ((red - 1) / (drawn - 1))


def check_vector_magnitude(params, question):
    x, y = floats(r"components \((-?[\d.]+), (-?[\d.]+)\)", question)
    return math.hypot(x, y)


def check_reflect_and_translate(params, question):
    px, py, hx, hy = ints(
        r"P\((-?\d+), (-?\d+)\) is reflected in the x-axis and the image is "
        r"then translated by the vector \((-?\d+), (-?\d+)\)",
        question,
    )
    # Reflection in the x-axis fixes x and negates y; then the translation.
    return f"{px + hx}, {-py + hy}"


# ------------------------------------------------------------------- physics


def check_uniform_acceleration_velocity(params, question):
    u, a, t = floats(
        r"velocity of ([\d.]+) m/s and accelerates uniformly at ([\d.]+) "
        r"m/s\^2 for ([\d.]+) s",
        question,
    )
    return u + a * t


def check_free_fall_time(params, question):
    (height,) = floats(r"height of ([\d.]+) m", question)
    assert "g = 10 m/s^2" in question, "the question does not say which g"
    return math.sqrt(2.0 * height / G)


def check_newton_second_law(params, question):
    mass, u, v, t = floats(
        r"mass ([\d.]+) kg, changing its velocity from ([\d.]+) m/s to "
        r"([\d.]+) m/s in ([\d.]+) s",
        question,
    )
    return mass * (v - u) / t


def check_momentum_collision(params, question):
    m1, u1, m2 = floats(
        r"mass ([\d.]+) kg moving at ([\d.]+) m/s collides with a stationary "
        r"body of mass ([\d.]+) kg",
        question,
    )
    assert m2 > 0, "the stationary body has no mass"
    return m1 * u1 / (m1 + m2)


def check_work_and_power(params, question):
    mass, height, time = floats(
        r"mass ([\d.]+) kg is raised through a height of ([\d.]+) m in "
        r"([\d.]+) s",
        question,
    )
    assert "g = 10 m/s^2" in question, "the question does not say which g"
    return mass * G * height / time


def check_machine_efficiency(params, question):
    velocity_ratio, effort, load = floats(
        r"velocity ratio of ([\d.]+) uses an effort of ([\d.]+) N to raise a "
        r"load of ([\d.]+) N",
        question,
    )
    advantage = load / effort
    efficiency = advantage / velocity_ratio * 100.0
    assert 0 < efficiency <= 100, (
        f"efficiency of {efficiency} per cent -- a machine that gives out more "
        f"than it takes in is not something to practise on"
    )
    return efficiency


def check_pressure_in_a_liquid(params, question):
    depth, density = floats(
        r"depth of ([\d.]+) m in a liquid of density ([\d.]+) kg/m\^3", question
    )
    assert "g = 10 m/s^2" in question, "the question does not say which g"
    return density * G * depth


def check_heat_capacity(params, question):
    grams, capacity, rise = floats(
        r"temperature of ([\d.]+) g of a substance of specific heat capacity "
        r"([\d.]+) J/kg/K by ([\d.]+) K",
        question,
    )
    return (grams / 1000.0) * capacity * rise


def check_wave_equation(params, question):
    frequency, wavelength = floats(
        r"frequency ([\d.]+) Hz has a wavelength of ([\d.]+) m", question
    )
    return frequency * wavelength


def check_resistors_in_parallel(params, question):
    r1, r2 = floats(r"resistors of ([\d.]+) ohms and ([\d.]+) ohms", question)
    combined = 1.0 / (1.0 / r1 + 1.0 / r2)
    assert combined < min(r1, r2), "a parallel pair is smaller than either resistor"
    return combined


def check_ohms_law_power(params, question):
    voltage, resistance = floats(
        r"potential difference of ([\d.]+) V is applied across a resistor of "
        r"([\d.]+) ohms",
        question,
    )
    # P = V^2/R, which is the same physics by a different route from V x I.
    return voltage * voltage / resistance


def check_transformer_turns(params, question):
    primary_turns, secondary_turns, primary_voltage = floats(
        r"has ([\d.]+) turns in its primary coil and ([\d.]+) turns in its "
        r"secondary coil\. If the primary is connected to a ([\d.]+) V supply",
        question,
    )
    return primary_voltage * secondary_turns / primary_turns


def check_half_life_remaining(params, question):
    initial, half_life, elapsed = floats(
        r"mass ([\d.]+) g has a half-life of ([\d.]+) days\. What mass remains "
        r"after ([\d.]+) days",
        question,
    )
    return initial * 0.5 ** (elapsed / half_life)



# ----------------------------------------------------------------- chemistry
#
# The relative atomic masses are written out again here rather than imported,
# so a template and its check cannot agree on a wrong mass. This is the table
# CHM A0 publishes.

MASSES = {
    "H": 1.0, "C": 12.0, "N": 14.0, "O": 16.0, "Na": 23.0, "Mg": 24.0,
    "S": 32.0, "Cl": 35.5, "K": 39.0, "Ca": 40.0, "Fe": 56.0, "Cu": 64.0,
    "Zn": 65.0, "Ag": 108.0,
}

MOLAR_VOLUME = 22.4
FARADAY_C = 96500.0

ELEMENT = re.compile(r"([A-Z][a-z]?)(\d*)")


def molar_mass(formula: str) -> float:
    """Sum a relative molecular mass from the formula the student is shown.

    Parsed from the printed string rather than looked up by name, so a
    template that prints one formula and weighs another is caught. Handles
    the single bracketed case in the set, Ca(OH)2.
    """
    bracket = re.fullmatch(r"([A-Za-z0-9]*)\(([A-Za-z0-9]+)\)(\d+)([A-Za-z0-9]*)",
                           formula)
    if bracket:
        before, inside, multiplier, after = bracket.groups()
        total = int(multiplier) * molar_mass(inside)
        if before:
            total += molar_mass(before)
        if after:
            total += molar_mass(after)
        return total

    total = 0.0
    consumed = 0
    for element, count in ELEMENT.findall(formula):
        assert element in MASSES, f"unknown element {element!r} in {formula!r}"
        total += MASSES[element] * (int(count) if count else 1)
        consumed += len(element) + len(count)
    assert consumed == len(formula), f"could not fully parse {formula!r}"
    return total


def check_moles_from_mass(params, question):
    mass, formula = grab(r"in ([\d.]+) g of [^,]+, ([A-Za-z0-9()]+)\.", question)
    return float(mass) / molar_mass(formula)


def check_mass_from_moles(params, question):
    moles, formula = grab(r"of ([\d.]+) mol of [^,]+, ([A-Za-z0-9()]+)\?", question)
    return float(moles) * molar_mass(formula)


def check_relative_molecular_mass(params, question):
    (formula,) = grab(r"mass of [^,]+, ([A-Za-z0-9()]+)\.", question)
    return molar_mass(formula)


def check_moles_from_gas_volume(params, question):
    (volume,) = floats(r"in ([\d.]+) dm3 of", question)
    return volume / MOLAR_VOLUME


def check_concentration_mol_per_dm3(params, question):
    mass, formula = grab(r"^([\d.]+) g of [^,]+, ([A-Za-z0-9()]+),", question)
    (volume_cm3,) = floats(r"up to ([\d.]+) cm3", question)
    return (float(mass) / molar_mass(formula)) / (volume_cm3 / 1000.0)


def check_concentration_g_per_dm3(params, question):
    (formula,) = grab(r"A solution of [^,]+, ([A-Za-z0-9()]+),", question)
    (molar,) = floats(r"concentration of ([\d.]+) mol/dm3", question)
    return molar * molar_mass(formula)


def check_dilution(params, question):
    from_cm3, start, to_cm3 = floats(
        r"^([\d.]+) cm3 of a ([\d.]+) mol/dm3 solution is diluted with water "
        r"to ([\d.]+) cm3",
        question,
    )
    assert to_cm3 > from_cm3, "diluting must increase the volume"
    return start * from_cm3 / to_cm3


def check_titration_concentration(params, question):
    base_cm3, base_conc = floats(r"^([\d.]+) cm3 of ([\d.]+) mol/dm3", question)
    (acid_cm3,) = floats(r"required ([\d.]+) cm3 of hydrochloric", question)
    # The mole ratio is read off the printed equation rather than off params.
    # Missing the 2 in front of HCl is exactly the mistake this question is
    # set to catch, so the check has to make it possible to make.
    (equation,) = grab(r"The equation is (.+?)\. Calculate", question)
    acid_coefficient = 2 if re.search(r"\b2HCl\b", equation) else 1
    base_moles = base_conc * base_cm3 / 1000.0
    return (base_moles * acid_coefficient) / (acid_cm3 / 1000.0)


def check_percentage_purity(params, question):
    sample, pure = floats(
        r"A ([\d.]+) g sample .*? contain ([\d.]+) g of the pure", question
    )
    assert pure <= sample, "a sample cannot hold more pure compound than it weighs"
    return pure / sample * 100.0


def check_percentage_yield(params, question):
    theoretical, actual = floats(
        r"give ([\d.]+) g of product actually gives ([\d.]+) g", question
    )
    assert actual <= theoretical, "a yield cannot beat the theoretical maximum"
    return actual / theoretical * 100.0


def check_electrolysis_mass(params, question):
    current, seconds = floats(
        r"current of ([\d.]+) A is passed for ([\d.]+) s", question
    )
    electrons, metal = grab(r"\+ (\d)e- -> ([A-Z][a-z]?)\.", question)
    (stated,) = floats(r"\[[A-Z][a-z]? = ([\d.]+);", question)
    assert stated == MASSES[metal], (
        f"the question states {metal} = {stated}, the table says {MASSES[metal]}"
    )
    moles_of_electrons = current * seconds / FARADAY_C
    return (moles_of_electrons / int(electrons)) * MASSES[metal]


def check_heat_of_reaction(params, question):
    volume, rise = floats(
        r"^([\d.]+) cm3 of solution .*? rises by ([\d.]+) degrees", question
    )
    # The question states a density of 1 g/cm3, so the mass in grams is the
    # volume in cm3, and a specific heat capacity of 4.2 J/g/K.
    return volume * 4.2 * rise


def check_rate_of_reaction(params, question):
    start, end, seconds = floats(
        r"falls from ([\d.]+) mol/dm3 to ([\d.]+) mol/dm3 in ([\d.]+) s",
        question,
    )
    assert start > end, "the concentration of a reactant must fall"
    return (start - end) / seconds


def check_gas_law_volume(params, question):
    volume, celsius, pressure = floats(
        r"^([\d.]+) cm3 of a gas is collected at ([\d.]+) degrees Celsius and "
        r"([\d.]+) mmHg",
        question,
    )
    kelvin = celsius + 273.0
    return Rounded(pressure * volume * 273.0 / (kelvin * 760.0), 1)


CHECKERS: dict[str, Callable[[dict[str, Any], str], Any]] = {
    "base-to-ten": check_base_to_ten,
    "standard-form-product": check_standard_form_product,
    "percentage-error": check_percentage_error,
    "index-equation": check_index_equation,
    "fractional-index": check_fractional_index,
    "logarithm-from-given": check_logarithm_from_given,
    "logarithmic-equation": check_logarithmic_equation,
    "two-set-venn": check_two_set_venn,
    "simplify-surd": check_simplify_surd,
    "arithmetic-progression": check_arithmetic_progression,
    "geometric-progression": check_geometric_progression,
    "sum-to-infinity": check_sum_to_infinity,
    "matrix-determinant": check_matrix_determinant,
    "simple-interest-principal": check_simple_interest_principal,
    "compound-interest-amount": check_compound_interest_amount,
    "hire-purchase-extra": check_hire_purchase_extra,
    "joint-variation": check_joint_variation,
    "factorise-trinomial-roots": check_factorise_trinomial_roots,
    "simultaneous-linear": check_simultaneous_linear,
    "change-of-subject": check_change_of_subject,
    "quadratic-roots": check_quadratic_roots,
    "sum-and-product-of-roots": check_sum_and_product_of_roots,
    "polygon-interior-sum": check_polygon_interior_sum,
    "polygon-from-exterior": check_polygon_from_exterior,
    "angle-at-centre": check_angle_at_centre,
    "cyclic-quadrilateral": check_cyclic_quadrilateral,
    "sector-area": check_sector_area,
    "cone-volume": check_cone_volume,
    "sphere-surface-area": check_sphere_surface_area,
    "cosine-rule-side": check_cosine_rule_side,
    "angle-of-elevation-height": check_angle_of_elevation_height,
    "gradient-at-a-point": check_gradient_at_a_point,
    "definite-integral": check_definite_integral,
    "grouped-mean": check_grouped_mean,
    "probability-without-replacement": check_probability_without_replacement,
    "vector-magnitude": check_vector_magnitude,
    "reflect-and-translate": check_reflect_and_translate,
    "uniform-acceleration-velocity": check_uniform_acceleration_velocity,
    "free-fall-time": check_free_fall_time,
    "newton-second-law": check_newton_second_law,
    "momentum-collision": check_momentum_collision,
    "work-and-power": check_work_and_power,
    "machine-efficiency": check_machine_efficiency,
    "pressure-in-a-liquid": check_pressure_in_a_liquid,
    "heat-capacity": check_heat_capacity,
    "wave-equation": check_wave_equation,
    "resistors-in-parallel": check_resistors_in_parallel,
    "ohms-law-power": check_ohms_law_power,
    "transformer-turns": check_transformer_turns,
    "half-life-remaining": check_half_life_remaining,
    # chemistry
    "moles-from-mass": check_moles_from_mass,
    "mass-from-moles": check_mass_from_moles,
    "relative-molecular-mass": check_relative_molecular_mass,
    "moles-from-gas-volume": check_moles_from_gas_volume,
    "concentration-mol-per-dm3": check_concentration_mol_per_dm3,
    "concentration-g-per-dm3": check_concentration_g_per_dm3,
    "dilution": check_dilution,
    "titration-concentration": check_titration_concentration,
    "percentage-purity": check_percentage_purity,
    "percentage-yield": check_percentage_yield,
    "electrolysis-mass": check_electrolysis_mass,
    "heat-of-reaction": check_heat_of_reaction,
    "rate-of-reaction": check_rate_of_reaction,
    "gas-law-volume": check_gas_law_volume,
}

# The four templates whose right answer is a fraction, and the two whose
# answer is more than one number. Everything else answers with one number.
FRACTION_ANSWERS = {
    "sum-and-product-of-roots",
    "definite-integral",
    "probability-without-replacement",
    "joint-variation",
}
MULTI_VALUE_KINDS = {"number_set": ",", "number_list": ","}


# ------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def registry() -> list:
    found = T.all_templates()
    assert found, "no practice templates registered"
    return found


@pytest.fixture(scope="module")
def corpus_front_matter() -> dict[str, dict]:
    """doc_id -> front matter, read straight off disk.

    Read with the corpus loader rather than from the database, so this test
    says whether the file a student would be sent to exists, not whether some
    ingest run once put a row in a table.
    """
    found: dict[str, dict] = {}
    for path in sorted(CORPUS.rglob("*.md")):
        try:
            document = load_file(path)
        except CorpusError:
            # A half-written draft elsewhere in the corpus is not this test's
            # business. If a template cites one, the citation test below says
            # so by name.
            continue
        found[document.doc_id] = {"locator": document.locator, "path": path}
    assert found, f"no corpus documents found under {CORPUS}"
    return found


def _built(template) -> list:
    return [template.sample(random.Random(seed)) for seed in SEEDS]


# ---------------------------------------------------------------- the answers


@pytest.mark.parametrize(
    "template_id",
    sorted(CHECKERS),
)
def test_the_computed_answer_is_the_right_one(template_id):
    """Recompute the answer from the question, over a spread of seeds."""
    template = T.get(template_id)
    assert template is not None, f"{template_id} is not registered"

    for seed in SEEDS:
        built = template.sample(random.Random(seed))
        expected = CHECKERS[template_id](built.params, built.question)
        context = (
            f"{template_id} seed {seed}: params {built.params!r}\n"
            f"  question: {built.question}\n"
            f"  generator answered {built.answer!r}"
        )

        if isinstance(expected, str):
            assert built.answer == expected, f"{context}; expected {expected!r}"

        elif isinstance(expected, Unordered):
            given = {number(part) for part in built.answer.split(",")}
            assert len(given) == len(expected.values), (
                f"{context}; expected {sorted(expected.values)}"
            )
            for wanted in expected.values:
                assert any(abs(wanted - g) < 1e-6 for g in given), (
                    f"{context}; expected {sorted(expected.values)}"
                )

        elif isinstance(expected, Rounded):
            got = number(built.answer)
            # The question says how many places, so half a unit in the last
            # place is exactly the tolerance it asked for.
            allowed = 0.5 * 10.0**-expected.places + 1e-9
            assert abs(got - expected.value) <= allowed, (
                f"{context}; recomputing gives {expected.value}"
            )
            assert decimal_places(built.answer) <= expected.places, (
                f"{context}; the question asked for {expected.places} decimal "
                f"places"
            )

        else:
            got = number(built.answer)
            assert abs(got - expected) <= 1e-9 * max(1.0, abs(expected)), (
                f"{context}; recomputing gives {expected}"
            )


def test_every_template_is_checked(registry):
    """A new template must arrive with a check, or this fails.

    Without it the suite quietly stops covering the registry as it grows,
    which is what makes a test suite look healthier than it is.
    """
    registered = {t.template_id for t in registry}
    missing = registered - set(CHECKERS)
    assert not missing, f"templates with no independent check: {sorted(missing)}"
    extra = set(CHECKERS) - registered
    assert not extra, f"checks for templates that no longer exist: {sorted(extra)}"


# ------------------------------------------------------------- the properties


@pytest.mark.parametrize("template_id", sorted(CHECKERS))
def test_params_survive_a_round_trip_through_jsonb(template_id):
    """`params` is stored as JSONB and rebuilt from the row.

    A tuple, a Fraction or a numpy integer in there would come back as
    something else and the question would silently change between the page
    that set it and the page that marks it.
    """
    template = T.get(template_id)
    for seed in SEEDS:
        built = template.sample(random.Random(seed))
        try:
            restored = json.loads(json.dumps(built.params))
        except (TypeError, ValueError) as e:
            pytest.fail(f"{template_id} seed {seed}: params are not JSON: {e}")

        again = template.rebuild(restored)
        where = f"{template_id} seed {seed}: params {built.params!r}"
        assert again.question == built.question, f"{where}: question changed"
        assert again.answer == built.answer, f"{where}: answer changed"
        assert again.working == built.working, f"{where}: working changed"
        assert again.answer_kind == built.answer_kind, f"{where}: kind changed"
        assert again.hint == built.hint, f"{where}: hint changed"


def test_every_citation_points_at_a_real_passage(registry, corpus_front_matter):
    """The doc a wrong answer sends a student to has to be there.

    This is the check that stops a template pointing a struggling student at a
    passage that does not exist, or at one whose locator no longer matches the
    citation the page renders.
    """
    for template in registry:
        entry = corpus_front_matter.get(template.source_doc_id)
        assert entry is not None, (
            f"{template.template_id} cites {template.source_doc_id}, which is "
            f"not a loadable document under {CORPUS}"
        )
        assert entry["locator"] == template.source_locator, (
            f"{template.template_id} cites locator "
            f"{template.source_locator!r}, but {entry['path'].name} says "
            f"{entry['locator']!r}"
        )


@pytest.mark.parametrize("template_id", sorted(CHECKERS))
def test_every_question_can_be_explained(template_id):
    """A hint and real working, on every variant.

    The working is what a student sees after a wrong answer, alongside the
    citation. One line of it is a restatement, not an explanation.
    """
    template = T.get(template_id)
    for seed in SEEDS:
        built = template.sample(random.Random(seed))
        where = f"{template_id} seed {seed}"
        assert built.hint.strip(), f"{where}: empty hint"
        assert len(built.working) >= 2, (
            f"{where}: only {len(built.working)} step(s) of working"
        )
        for step in built.working:
            assert step.strip(), f"{where}: a blank step of working"
        assert built.question.strip(), f"{where}: empty question"


@pytest.mark.parametrize("template_id", sorted(CHECKERS))
def test_the_answer_is_one_a_student_could_type(template_id):
    """Short, non-empty, and free of letters where it claims to be a number."""
    template = T.get(template_id)
    for seed in SEEDS:
        built = template.sample(random.Random(seed))
        where = f"{template_id} seed {seed}: answer {built.answer!r}"
        assert built.answer.strip(), f"{where}: empty answer"
        assert len(built.answer) <= MAX_ANSWER_LENGTH, (
            f"{where}: {len(built.answer)} characters is more than a student "
            f"will type on a phone"
        )
        assert built.answer_kind in {"number", "number_set", "number_list"}, (
            f"{where}: unknown answer kind {built.answer_kind!r}"
        )
        if built.answer_kind == "number":
            assert not re.search(r"[A-Za-z]", built.answer), (
                f"{where}: a number-kind answer contains a letter"
            )
            assert "," not in built.answer, (
                f"{where}: a single number should not contain a comma"
            )
            # Every one of these parses as a number, fraction form included.
            number(built.answer)
        else:
            parts = [p for p in built.answer.split(",")]
            assert len(parts) >= 2, f"{where}: {built.answer_kind} with one value"
            for part in parts:
                assert not re.search(r"[A-Za-z]", part), (
                    f"{where}: contains a letter"
                )
                number(part)


def test_subjects_and_boards_are_live_ones(registry):
    """Nothing draws practice from a subject that is not switched on."""
    for template in registry:
        assert template.subject in LIVE_SUBJECTS, (
            f"{template.template_id} is for {template.subject!r}, which is not "
            f"a live subject"
        )
        assert template.exam_board == LIVE_BOARD, (
            f"{template.template_id} is for board {template.exam_board!r}"
        )
        assert template.topic.strip(), f"{template.template_id} has no topic"
        assert template.subtopic.strip(), f"{template.template_id} has no subtopic"


def test_only_the_four_fraction_templates_answer_with_a_fraction(registry):
    """A fraction is right for four of these and a rough edge everywhere else.

    Not an arithmetic check -- a bare statement of which answers are meant to
    look like `3/8`, so a new one showing up somewhere else is noticed.
    """
    seen: set[str] = set()
    for template in registry:
        for seed in SEEDS:
            if "/" in template.sample(random.Random(seed)).answer:
                seen.add(template.template_id)
                break
    unexpected = seen - FRACTION_ANSWERS
    assert not unexpected, (
        f"these answer with a fraction and were not meant to: {sorted(unexpected)}"
    )


# ------------------------------------------------ questions that read wrong
#
# Each of these was a real defect when this file was written, and each is
# fixed. None was an arithmetic error -- every recomputed answer came out
# right -- which is exactly why they are worth keeping: a suite that only
# checks the arithmetic passes a question that names the roots of an
# equation with no real roots, or asks a student to evaluate 4^(2/2).
#
# They stay as ordinary tests rather than being deleted with the bugs,
# because the sampling constraints that fix them are one careless edit away
# from being removed again.


def _every_question(template_id: str, seeds=range(400)):
    template = T.get(template_id)
    for seed in seeds:
        yield seed, template.sample(random.Random(seed))


ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}


def _right_suffix(value: int) -> str:
    if 11 <= value % 100 <= 13:
        return "th"
    return ORDINAL_SUFFIXES.get(value % 10, "th")


def test_ordinals_in_questions_are_written_correctly():
    wrong: list[str] = []
    for template in T.all_templates():
        for seed in range(200):
            question = template.sample(random.Random(seed)).question
            for found in re.finditer(r"(\d+)(st|nd|rd|th)\b", question):
                value, suffix = int(found.group(1)), found.group(2)
                if suffix != _right_suffix(value):
                    wrong.append(
                        f"{template.template_id} seed {seed}: "
                        f"{value}{suffix} should be {value}{_right_suffix(value)}"
                    )
    assert not wrong, f"{len(wrong)} ungrammatical ordinals, e.g. {wrong[:3]}"


def test_a_fractional_index_question_has_a_fractional_index():
    flat: list[str] = []
    for seed, built in _every_question("fractional-index"):
        _, power, root = ints(r"Evaluate (\d+)\^\((\d+)/(\d+)\)", built.question)
        if power % root == 0:
            flat.append(f"seed {seed}: {built.question}")
    assert not flat, f"{len(flat)} variants are not fractional, e.g. {flat[:3]}"


@pytest.mark.parametrize(
    "template_id,pattern,what",
    [
        (
            "simultaneous-linear",
            r"\b1[xy]\b",
            "prints a unit coefficient as '1x' or '1y' -- 'Solve 1x + 1y = 5'",
        ),
        (
            "definite-integral",
            r"\b[01]x\b",
            "prints '1x^2' and '+ 0x' in the integrand",
        ),
        (
            "index-equation",
            r"x \+ 0\)",
            "prints a zero offset, as in '2^(2x + 0) = 64'",
        ),
    ],
)
def test_expressions_are_printed_the_way_a_paper_prints_them(
    template_id, pattern, what
):
    offenders = [
        f"seed {seed}: {built.question}"
        for seed, built in _every_question(template_id)
        if re.search(pattern, built.question)
    ]
    assert not offenders, (
        f"{template_id} {what}: {len(offenders)} variants, e.g. {offenders[:2]}"
    )


def test_a_question_about_the_roots_of_a_quadratic_has_roots():
    imaginary: list[str] = []
    for seed, built in _every_question("sum-and-product-of-roots"):
        (expression,) = grab(r"The roots of (.+?) = 0 are alpha", built.question)
        terms = polynomial(expression)
        a, b, c = terms.get(2, 0), terms.get(1, 0), terms.get(0, 0)
        if b * b - 4 * a * c < 0:
            imaginary.append(f"seed {seed}: {expression} = 0")
    assert not imaginary, (
        f"{len(imaginary)} variants have no real roots, e.g. {imaginary[:3]}"
    )
