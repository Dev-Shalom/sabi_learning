"""Mathematics practice templates.

One function per question shape. Each samples its own numbers, subject to
whatever constraint keeps the answer clean, and then computes the answer --
never states it. Where a constraint exists it is written next to the working
it protects, because the two go wrong together.

`n()` from `templates` does all the printing, so an answer string is always
one a student could plausibly have typed.
"""

from __future__ import annotations

import math
import random
from fractions import Fraction
from typing import Any

from sabi.practice.templates import PI, Built, n, template

SQUAREFREE = (2, 3, 5, 6, 7, 10, 11)


def _ordinal(value: int) -> str:
    """3rd, not 3th.

    Small, but it is the first thing on the page: a student who reads "the
    3th term" has been told the question was not proofread, and stops
    trusting the rest of it.
    """
    if 10 <= value % 100 <= 20:
        return f"{value}th"
    return f"{value}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(value % 10, 'th')}"


def _term(coefficient: int, symbol: str) -> str:
    """`x`, not `1x`. The leading term of an expression, with its sign."""
    size = "" if abs(coefficient) == 1 else str(abs(coefficient))
    return f"{'-' if coefficient < 0 else ''}{size}{symbol}"


def _joined(coefficient: int, symbol: str) -> str:
    """` + 3y`, ` - y`, or nothing at all when the coefficient is zero."""
    if coefficient == 0:
        return ""
    size = "" if abs(coefficient) == 1 else str(abs(coefficient))
    return f" {'+' if coefficient > 0 else '-'} {size}{symbol}"


def _joined_constant(value: int) -> str:
    """` + 5`, ` - 1`, or nothing when it is zero.

    Separate from `_joined` because that one drops a coefficient of 1 -- `y`
    means `1y` -- which is right for a term carrying a symbol and turns
    `2x - 1` into `2x - ` for one that does not.
    """
    return "" if value == 0 else f" {'+' if value > 0 else '-'} {abs(value)}"


# --------------------------------------------------- number and numeration


@template(
    "base-to-ten",
    doc="ex-01-number-base-to-ten",
    locator="EX 01",
    topic="Number and numeration",
    subtopic="Number bases",
)
def base_to_ten(rng, params=None) -> Built:
    if params is None:
        base = rng.randint(3, 8)
        digits = [rng.randint(1, base - 1)] + [
            rng.randint(0, base - 1) for _ in range(rng.randint(2, 3))
        ]
        params = {"base": base, "digits": digits}
    base, digits = params["base"], list(params["digits"])

    value = 0
    for digit in digits:
        value = value * base + digit
    shown = "".join(str(d) for d in digits)

    return Built(
        params=params,
        question=(
            f"Convert {shown} from base {base} to base ten."
        ),
        answer=n(value),
        hint="Give a whole number in base ten.",
        working=(
            f"Write each digit with its place value, the largest power of "
            f"{base} first.",
            " + ".join(
                f"{d} x {base}^{len(digits) - 1 - i}" for i, d in enumerate(digits)
            ),
            f"= {value}.",
        ),
    )


@template(
    "standard-form-product",
    doc="ex-04-standard-form",
    locator="EX 04",
    topic="Number and numeration",
    subtopic="Approximation and standard form",
)
def standard_form_product(rng, params=None) -> Built:
    if params is None:
        params = {
            "a": rng.randint(2, 9),
            "b": rng.randint(2, 9),
            "p": rng.randint(2, 5),
            "q": rng.randint(-4, -1),
        }
    a, b, p, q = params["a"], params["b"], params["p"], params["q"]

    value = Fraction(a * b) * Fraction(10) ** (p + q)

    return Built(
        params=params,
        question=(
            f"Evaluate ({a} x 10^{p}) x ({b} x 10^{q}), giving your answer as "
            f"an ordinary number."
        ),
        answer=n(value),
        hint="Give an ordinary number, not standard form.",
        working=(
            f"Multiply the numbers and add the powers: {a} x {b} = {a * b}, "
            f"and 10^{p} x 10^{q} = 10^{p + q}.",
            f"So the product is {a * b} x 10^{p + q} = {n(value)}.",
        ),
    )


@template(
    "percentage-error",
    doc="ex-05-percentage-error",
    locator="EX 05",
    topic="Number and numeration",
    subtopic="Approximation",
)
def percentage_error(rng, params=None) -> Built:
    if params is None:
        # Every true value here divides 100 exactly, so the percentage comes
        # out as a terminating decimal rather than a recurring one.
        params = {
            "true_value": rng.choice([25, 40, 50, 80, 125, 200, 250]),
            "error": rng.choice([-4, -3, -2, -1, 1, 2, 3, 4]),
        }
    true_value, error = params["true_value"], params["error"]
    measured = true_value + error

    percentage = Fraction(abs(error) * 100, true_value)

    return Built(
        params=params,
        question=(
            f"A length whose true value is {true_value} cm is measured as "
            f"{measured} cm. Find the percentage error."
        ),
        answer=n(percentage),
        hint="Give the percentage, without the % sign.",
        working=(
            f"Error = |{measured} - {true_value}| = {abs(error)} cm.",
            f"Percentage error = error / true value x 100 = "
            f"{abs(error)}/{true_value} x 100.",
            f"= {n(percentage)} per cent.",
        ),
    )


@template(
    "index-equation",
    doc="ex-06-index-equation",
    locator="EX 06",
    topic="Number and numeration",
    subtopic="Indices",
)
def index_equation(rng, params=None) -> Built:
    if params is None:
        base = rng.choice([2, 3, 5])
        # The right-hand side is written out as an ordinary number, so the
        # power it represents has to stay small enough to read. Choosing the
        # power first and deriving the offset from it guarantees that,
        # whereas resampling the offset until it fits can never terminate --
        # 3x - 3 with x = 3 cannot reach a power of 5 below 4 at all.
        power = rng.randint(2, {2: 10, 3: 6, 5: 4}[base])
        coefficient = rng.randint(2, 3)
        x = rng.randint(2, 3)
        params = {
            "base": base,
            "coefficient": coefficient,
            "x": x,
            "offset": power - coefficient * x,
        }

    base = params["base"]
    coefficient, x, offset = params["coefficient"], params["x"], params["offset"]
    power = coefficient * x + offset
    rhs = base**power
    # `2x + 0` is not how anyone writes an index, so a zero offset drops out
    # of the printed expression. Not `_joined`: that suppresses a coefficient
    # of 1 because `y` means `1y`, which is right for a term with a symbol
    # and wrong for a bare number -- it turns `2x - 1` into `2x - `.
    index = f"{coefficient}x{_joined_constant(offset)}"

    return Built(
        params=params,
        question=f"Solve for x: {base}^({index}) = {rhs}.",
        answer=n(x),
        hint="Give the value of x.",
        working=(
            f"Write {rhs} as a power of {base}: {rhs} = {base}^{power}.",
            f"The bases match, so the powers are equal: {index} = {power}.",
            f"{coefficient}x = {power - offset}, so x = {x}.",
        ),
    )


@template(
    "fractional-index",
    doc="ex-07-fractional-indices",
    locator="EX 07",
    topic="Number and numeration",
    subtopic="Indices",
)
def fractional_index(rng, params=None) -> Built:
    if params is None:
        root = rng.choice([2, 3])
        base_root = rng.randint(2, 5) if root == 2 else rng.randint(2, 4)
        # The power must not be a multiple of the root, or the index is a
        # whole number wearing a disguise: 4^(2/2) is 4, and a student who
        # spots that has not practised fractional indices at all.
        params = {
            "root": root,
            "base_root": base_root,
            "power": rng.choice([3, 5]) if root == 2 else rng.choice([2, 4]),
        }
    root, base_root, power = params["root"], params["base_root"], params["power"]

    base = base_root**root
    value = base_root**power

    return Built(
        params=params,
        question=f"Evaluate {base}^({power}/{root}).",
        answer=n(value),
        hint="Give a whole number.",
        working=(
            f"The denominator is the root: the {root} root of {base} is "
            f"{base_root}.",
            f"The numerator is the power: {base_root}^{power} = {value}.",
        ),
    )


@template(
    "logarithm-from-given",
    doc="ex-08-logarithm-from-given-values",
    locator="EX 08",
    topic="Number and numeration",
    subtopic="Logarithms",
)
def logarithm_from_given(rng, params=None) -> Built:
    if params is None:
        params = {"twos": rng.randint(0, 4), "threes": rng.randint(0, 2)}
        while params["twos"] + params["threes"] == 0:
            params = {"twos": rng.randint(1, 4), "threes": rng.randint(0, 2)}
    twos, threes = params["twos"], params["threes"]

    value = 2**twos * 3**threes
    # Worked in exact quarters of a ten-thousandth so the final rounding is
    # the only rounding, matching how a student uses a four-figure table.
    total = twos * Fraction(3010, 10000) + threes * Fraction(4771, 10000)

    # Printed to four places explicitly rather than through `n`, which shows
    # a terminating fraction exactly and so drops the trailing zero of
    # 1.2040 -- leaving the answer disagreeing with the hint above it.
    shown = f"{float(total):.4f}"

    # A student reading this back after a wrong answer should not be shown
    # `3^0` and `0 log 3`; when a factor is absent it is left out.
    factors = " x ".join(
        f"{base}^{power}"
        for base, power in ((2, twos), (3, threes))
        if power
    )
    terms = " + ".join(
        f"{power} log {base}"
        for base, power in ((2, twos), (3, threes))
        if power
    )

    return Built(
        params=params,
        question=(
            f"Given that log 2 = 0.3010 and log 3 = 0.4771, evaluate log {value}."
        ),
        answer=shown,
        hint="Give your answer to four decimal places.",
        working=(
            f"Write {value} in prime factors: {value} = {factors}.",
            f"log {value} = {terms}.",
            f"= {shown}.",
        ),
    )


@template(
    "logarithmic-equation",
    doc="ex-09-logarithmic-equation",
    locator="EX 09",
    topic="Number and numeration",
    subtopic="Logarithms",
)
def logarithmic_equation(rng, params=None) -> Built:
    if params is None:
        base = rng.choice([2, 3, 5, 10])
        params = {"base": base, "power": rng.randint(2, 4 if base > 2 else 6)}
    base, power = params["base"], params["power"]
    value = base**power

    return Built(
        params=params,
        question=f"Solve for x: log base {base} of x = {power}.",
        answer=n(value),
        hint="Give the value of x.",
        working=(
            f"log base {base} of x = {power} means x = {base}^{power}.",
            f"x = {value}.",
        ),
    )


@template(
    "two-set-venn",
    doc="ex-10-two-set-venn",
    locator="EX 10",
    topic="Number and numeration",
    subtopic="Sets",
)
def two_set_venn(rng, params=None) -> Built:
    if params is None:
        total = rng.randint(30, 60)
        both = rng.randint(4, 12)
        # Everyone takes at least one subject, so the two counts have to
        # overlap by exactly `both` and cover the class between them.
        only_first = rng.randint(8, total - both - 8)
        params = {"total": total, "both": both, "only_first": only_first}

    total, both, only_first = params["total"], params["both"], params["only_first"]
    only_second = total - both - only_first
    first = only_first + both
    second = only_second + both

    return Built(
        params=params,
        question=(
            f"In a class of {total} students, {first} offer Mathematics and "
            f"{second} offer Physics. Every student offers at least one of the "
            f"two. How many offer both subjects?"
        ),
        answer=n(both),
        hint="Give the number of students.",
        working=(
            "n(M or P) = n(M) + n(P) - n(M and P), and everyone offers at "
            "least one, so n(M or P) is the whole class.",
            f"{total} = {first} + {second} - n(M and P).",
            f"n(M and P) = {first} + {second} - {total} = {both}.",
        ),
    )


@template(
    "simplify-surd",
    doc="ex-12-simplify-surds",
    locator="EX 12",
    topic="Number and numeration",
    subtopic="Surds",
)
def simplify_surd(rng, params=None) -> Built:
    if params is None:
        params = {
            "outside": rng.randint(2, 6),
            "inside": rng.choice(SQUAREFREE),
        }
    outside, inside = params["outside"], params["inside"]
    value = outside * outside * inside

    return Built(
        params=params,
        question=(
            f"Simplify the square root of {value} in the form a root {inside}, "
            f"where a is a whole number. Find a."
        ),
        answer=n(outside),
        hint="Give the whole number a.",
        working=(
            f"Split {value} into a perfect square times {inside}: "
            f"{value} = {outside * outside} x {inside}.",
            f"The square root of {outside * outside} is {outside}, so the "
            f"surd is {outside} root {inside}.",
            f"a = {outside}.",
        ),
    )


@template(
    "arithmetic-progression",
    doc="ex-14-arithmetic-progression",
    locator="EX 14",
    topic="Number and numeration",
    subtopic="Sequences and series",
)
def arithmetic_progression(rng, params=None) -> Built:
    if params is None:
        params = {
            "first": rng.randint(2, 12),
            "difference": rng.randint(2, 9),
            "m": rng.randint(3, 6),
            "gap": rng.randint(3, 6),
            "terms": rng.choice([10, 12, 15, 20]),
        }
    first, difference = params["first"], params["difference"]
    m, gap, terms = params["m"], params["gap"], params["terms"]
    p = m + gap

    term_m = first + (m - 1) * difference
    term_p = first + (p - 1) * difference
    total = Fraction(terms, 2) * (2 * first + (terms - 1) * difference)

    return Built(
        params=params,
        question=(
            f"The {_ordinal(m)} term of an arithmetic progression is {term_m} "
            f"and the {_ordinal(p)} term is {term_p}. Find the sum of the "
            f"first {terms} terms."
        ),
        answer=n(total),
        hint="Give the sum.",
        working=(
            f"T{p} - T{m} = {p - m}d, so {term_p} - {term_m} = {p - m}d and "
            f"d = {difference}.",
            f"T{m} = a + {m - 1}d gives {term_m} = a + {(m - 1) * difference}, "
            f"so a = {first}.",
            f"S{terms} = ({terms}/2)(2a + {terms - 1}d) = {n(total)}.",
        ),
    )


@template(
    "geometric-progression",
    doc="ex-15-geometric-progression",
    locator="EX 15",
    topic="Number and numeration",
    subtopic="Sequences and series",
)
def geometric_progression(rng, params=None) -> Built:
    if params is None:
        params = {
            "first": rng.randint(2, 6),
            "ratio": rng.choice([2, 3]),
            "term": rng.randint(5, 7),
        }
    first, ratio, term = params["first"], params["ratio"], params["term"]
    value = first * ratio ** (term - 1)

    return Built(
        params=params,
        question=(
            f"The first term of a geometric progression is {first} and the "
            f"common ratio is {ratio}. Find the {_ordinal(term)} term."
        ),
        answer=n(value),
        hint="Give the term.",
        working=(
            f"Tn = ar^(n-1), so T{term} = {first} x {ratio}^{term - 1}.",
            f"{ratio}^{term - 1} = {ratio ** (term - 1)}.",
            f"T{term} = {value}.",
        ),
    )


@template(
    "sum-to-infinity",
    doc="ex-16-sum-to-infinity",
    locator="EX 16",
    topic="Number and numeration",
    subtopic="Sequences and series",
)
def sum_to_infinity(rng, params=None) -> Built:
    if params is None:
        denominator = rng.randint(2, 5)
        # a is chosen as a multiple of (k - 1) so that a / (1 - 1/k), which is
        # ak/(k - 1), comes out whole.
        params = {
            "denominator": denominator,
            "first": (denominator - 1) * rng.randint(3, 9),
        }
    denominator, first = params["denominator"], params["first"]
    ratio = Fraction(1, denominator)
    total = Fraction(first) / (1 - ratio)

    return Built(
        params=params,
        question=(
            f"The first term of a geometric progression is {first} and the "
            f"common ratio is 1/{denominator}. Find the sum to infinity."
        ),
        answer=n(total),
        hint="Give the sum to infinity.",
        working=(
            "S to infinity = a / (1 - r), valid because |r| < 1.",
            f"= {first} / (1 - 1/{denominator}) = {first} / "
            f"({denominator - 1}/{denominator}).",
            f"= {n(total)}.",
        ),
    )


@template(
    "matrix-determinant",
    doc="ex-17-matrix-determinant-inverse",
    locator="EX 17",
    topic="Number and numeration",
    subtopic="Matrices",
)
def matrix_determinant(rng, params=None) -> Built:
    if params is None:
        params = {k: rng.randint(-6, 8) for k in ("a", "b", "c", "d")}
    a, b, c, d = params["a"], params["b"], params["c"], params["d"]
    value = a * d - b * c

    return Built(
        params=params,
        question=(
            f"Find the determinant of the matrix with first row ({a}, {b}) and "
            f"second row ({c}, {d})."
        ),
        answer=n(value),
        hint="Give the determinant.",
        working=(
            "For a 2 by 2 matrix the determinant is ad - bc.",
            f"= ({a})({d}) - ({b})({c}) = {a * d} - {b * c}.",
            f"= {value}.",
        ),
    )


@template(
    "simple-interest-principal",
    doc="ex-19-simple-interest",
    locator="EX 19",
    topic="Number and numeration",
    subtopic="Financial arithmetic",
)
def simple_interest_principal(rng, params=None) -> Built:
    if params is None:
        params = {
            "principal": rng.choice([15000, 20000, 25000, 40000, 50000]),
            "rate": rng.choice([4, 5, 6, 8, 10]),
            "years": rng.randint(2, 5),
        }
    principal, rate, years = params["principal"], params["rate"], params["years"]
    interest = Fraction(principal * rate * years, 100)

    return Built(
        params=params,
        question=(
            f"Find the sum of money that will earn a simple interest of "
            f"{n(interest)} naira in {years} years at {rate} per cent per annum."
        ),
        answer=n(principal),
        hint="Give the principal in naira.",
        working=(
            "I = PRT/100, so P = 100I / (RT).",
            f"P = 100 x {n(interest)} / ({rate} x {years}).",
            f"P = {n(principal)} naira.",
        ),
    )


@template(
    "compound-interest-amount",
    doc="ex-20-compound-interest",
    locator="EX 20",
    topic="Number and numeration",
    subtopic="Financial arithmetic",
)
def compound_interest_amount(rng, params=None) -> Built:
    if params is None:
        params = {
            "principal": rng.choice([10000, 20000, 25000, 40000, 50000]),
            "rate": rng.choice([5, 10, 20, 25]),
            "years": rng.randint(2, 3),
        }
    principal, rate, years = params["principal"], params["rate"], params["years"]
    amount = Fraction(principal) * (1 + Fraction(rate, 100)) ** years

    return Built(
        params=params,
        question=(
            f"{n(principal)} naira is invested at {rate} per cent per annum "
            f"compound interest. Find the amount after {years} years."
        ),
        answer=n(amount),
        hint="Give the amount in naira.",
        working=(
            "A = P(1 + R/100)^n.",
            f"A = {n(principal)} x (1 + {rate}/100)^{years}.",
            f"A = {n(amount)} naira.",
        ),
    )


@template(
    "hire-purchase-extra",
    doc="ex-21-hire-purchase",
    locator="EX 21",
    topic="Number and numeration",
    subtopic="Financial arithmetic",
)
def hire_purchase_extra(rng, params=None) -> Built:
    if params is None:
        # The cash price is derived from the hire purchase price rather than
        # sampled alongside it, because sampling both independently produces
        # variants where hire purchase is the cheaper option -- true of the
        # arithmetic, false of the world, and confusing to practise on.
        params = {
            "deposit": rng.choice([10000, 12000, 15000, 20000]),
            "months": rng.choice([6, 9, 12]),
            "instalment": rng.choice([5000, 6000, 7500, 9000]),
            "extra": rng.choice([3000, 4500, 6000, 7500, 9000, 12000]),
        }
    deposit, months = params["deposit"], params["months"]
    instalment, extra = params["instalment"], params["extra"]

    total = deposit + months * instalment
    cash = total - extra

    return Built(
        params=params,
        question=(
            f"A television set costs {n(cash)} naira cash. On hire purchase a "
            f"buyer pays a deposit of {n(deposit)} naira and {months} monthly "
            f"instalments of {n(instalment)} naira. How much more than the cash "
            f"price does the buyer pay?"
        ),
        answer=n(extra),
        hint="Give the extra amount in naira.",
        working=(
            f"Hire purchase price = deposit + instalments = {n(deposit)} + "
            f"{months} x {n(instalment)} = {n(total)} naira.",
            f"Extra = {n(total)} - {n(cash)} = {n(extra)} naira.",
        ),
    )


@template(
    "joint-variation",
    doc="ex-22-joint-variation",
    locator="EX 22",
    topic="Number and numeration",
    subtopic="Variation",
)
def joint_variation(rng, params=None) -> Built:
    if params is None:
        params = {
            "k": rng.randint(2, 6),
            "x1": rng.randint(2, 6),
            "y1": rng.randint(2, 5),
            "x2": rng.randint(2, 8),
            "y2": rng.randint(2, 6),
        }
    k, x1, y1, x2, y2 = (params[key] for key in ("k", "x1", "y1", "x2", "y2"))

    z1 = k * x1 * y1 * y1
    z2 = Fraction(z1 * x2 * y2 * y2, x1 * y1 * y1)

    return Built(
        params=params,
        question=(
            f"z varies jointly as x and the square of y. When x = {x1} and "
            f"y = {y1}, z = {z1}. Find z when x = {x2} and y = {y2}."
        ),
        answer=n(z2),
        hint="Give the value of z.",
        working=(
            f"z = kxy^2, so k = z / (xy^2) = {z1} / ({x1} x {y1}^2) = {k}.",
            f"z = {k} x {x2} x {y2}^2.",
            f"z = {n(z2)}.",
        ),
    )


# ------------------------------------------------------- algebraic processes


@template(
    "factorise-trinomial-roots",
    doc="ex-24-factorise-trinomial",
    locator="EX 24",
    topic="Algebraic processes",
    subtopic="Factorisation",
)
def factorise_trinomial_roots(rng, params=None) -> Built:
    if params is None:
        first, second = rng.randint(-9, 9), rng.randint(-9, 9)
        # Distinct roots, and neither zero, so the factorisation is a genuine
        # trinomial with two different answers to give.
        while first == second or first == 0 or second == 0:
            first, second = rng.randint(-9, 9), rng.randint(-9, 9)
        params = {"root_a": first, "root_b": second}
    root_a, root_b = params["root_a"], params["root_b"]

    b = -(root_a + root_b)
    c = root_a * root_b
    equation = _quadratic_text(1, b, c)

    return Built(
        params=params,
        question=(
            f"Factorise {equation} and hence give the two values of x for which "
            f"it is zero."
        ),
        answer=f"{root_a}, {root_b}",
        answer_kind="number_set",
        hint="Give both values, separated by a comma. Order does not matter.",
        working=(
            f"Find two numbers that multiply to {c} and add to {b}: "
            f"{-root_a} and {-root_b}.",
            f"So the expression factorises as (x - {root_a})(x - {root_b}), "
            f"written with the signs worked through.",
            f"It is zero when x = {root_a} or x = {root_b}.",
        ),
    )


@template(
    "simultaneous-linear",
    doc="ex-26-simultaneous-linear",
    locator="EX 26",
    topic="Algebraic processes",
    subtopic="Simultaneous equations",
)
def simultaneous_linear(rng, params=None) -> Built:
    if params is None:
        params = {
            "x": rng.randint(-6, 8),
            "y": rng.randint(-6, 8),
            "a1": rng.randint(1, 5),
            "b1": rng.randint(1, 5),
            "a2": rng.randint(1, 5),
            "b2": rng.randint(-5, -1),
        }
    x, y = params["x"], params["y"]
    a1, b1, a2, b2 = params["a1"], params["b1"], params["a2"], params["b2"]

    c1 = a1 * x + b1 * y
    c2 = a2 * x + b2 * y

    return Built(
        params=params,
        question=(
            f"Solve the simultaneous equations "
            f"{_term(a1, 'x')}{_joined(b1, 'y')} = {c1} and "
            f"{_term(a2, 'x')}{_joined(b2, 'y')} = {c2}. Give the value of x."
        ),
        answer=n(x),
        hint="Give the value of x only.",
        working=(
            f"Multiply the first equation by {abs(b2)} and the second by {b1} "
            f"so the y terms cancel when the equations are added.",
            f"That gives x = {x}.",
            f"Substituting back gives y = {y}, which checks in both equations.",
        ),
    )


@template(
    "change-of-subject",
    doc="ex-27-change-of-subject",
    locator="EX 27",
    topic="Algebraic processes",
    subtopic="Change of subject",
)
def change_of_subject(rng, params=None) -> Built:
    if params is None:
        params = {
            "u": rng.choice([0, 2, 4, 5, 6, 10]),
            "a": rng.choice([2, 3, 4, 5]),
            "s": rng.choice([4, 6, 8, 10, 12]),
        }
    u, a, s = params["u"], params["a"], params["s"]

    v_squared = u * u + 2 * a * s
    v = math.isqrt(v_squared)
    # Only report an exact v when the square root is whole; otherwise the
    # question would be asking for a rounded input, which hides the algebra.
    exact = v * v == v_squared
    if not exact:
        v = None

    shown_v = n(v) if exact else n(math.sqrt(v_squared), places=4)
    value = Fraction(v_squared - u * u, 2 * s)

    return Built(
        params=params,
        question=(
            f"Make a the subject of the formula v^2 = u^2 + 2as, and find a "
            f"when v^2 = {v_squared}, u = {u} and s = {s}."
        ),
        answer=n(value),
        hint="Give the value of a.",
        working=(
            "v^2 - u^2 = 2as, so a = (v^2 - u^2) / (2s).",
            f"a = ({v_squared} - {u * u}) / (2 x {s}) = "
            f"{v_squared - u * u} / {2 * s}.",
            f"a = {n(value)}.",
        )
        + ((f"(v itself is {shown_v}.)",) if exact else ()),
    )


@template(
    "quadratic-roots",
    doc="ex-28-quadratic-formula",
    locator="EX 28",
    topic="Algebraic processes",
    subtopic="Quadratic equations",
)
def quadratic_roots(rng, params=None) -> Built:
    if params is None:
        first, second = rng.randint(-8, 8), rng.randint(-8, 8)
        while first == second:
            first, second = rng.randint(-8, 8), rng.randint(-8, 8)
        params = {
            "lead": rng.choice([1, 1, 2, 3]),
            "root_a": first,
            "root_b": second,
        }
    lead, root_a, root_b = params["lead"], params["root_a"], params["root_b"]

    b = -lead * (root_a + root_b)
    c = lead * root_a * root_b
    equation = _quadratic_text(lead, b, c)
    discriminant = b * b - 4 * lead * c

    return Built(
        params=params,
        question=f"Solve the equation {equation} = 0.",
        answer=f"{root_a}, {root_b}",
        answer_kind="number_set",
        hint="Give both roots, separated by a comma. Order does not matter.",
        working=(
            f"Here a = {lead}, b = {b} and c = {c}.",
            f"The discriminant is b^2 - 4ac = {b * b} - {4 * lead * c} = "
            f"{discriminant}, and its square root is "
            f"{n(math.isqrt(discriminant))}.",
            f"x = (-b +/- root(b^2 - 4ac)) / 2a gives x = {root_a} or "
            f"x = {root_b}.",
        ),
    )


@template(
    "sum-and-product-of-roots",
    doc="ex-30-sum-product-of-roots",
    locator="EX 30",
    topic="Algebraic processes",
    subtopic="Quadratic equations",
)
def sum_and_product_of_roots(rng, params=None) -> Built:
    if params is None:
        # Vieta's formulas hold whatever the discriminant is, so an
        # unconstrained sample gives a correct answer to a false question:
        # "the roots of 3x^2 + 9x + 8 = 0 are alpha and beta" names two real
        # roots of an equation that has none. Telling an SS3 student that is
        # exactly the confident wrongness this product exists to avoid, and
        # it is not caught by checking the arithmetic, because the
        # arithmetic is right.
        #
        # So c is drawn from the range that actually leaves two distinct
        # real roots -- c < b^2/4a -- rather than sampled and rejected,
        # which keeps this a fixed amount of work.
        lead = rng.randint(2, 5)
        b = rng.choice([x for x in range(-9, 10) if x != 0])
        highest = -(-(b * b) // (4 * lead)) - 1  # ceil(b^2/4a) - 1
        params = {
            "lead": lead,
            "b": b,
            # Zero is excluded as well: 3x^2 - 6 = 0 is a true question but a
            # degenerate one, and it stops the template testing what it is for.
            "c": rng.choice([x for x in range(-9, min(9, highest) + 1) if x != 0]),
            "want": rng.choice(["sum", "product"]),
        }
    lead, b, c, want = params["lead"], params["b"], params["c"], params["want"]
    equation = _quadratic_text(lead, b, c)

    value = Fraction(-b, lead) if want == "sum" else Fraction(c, lead)
    phrase = "sum" if want == "sum" else "product"
    rule = "-b/a" if want == "sum" else "c/a"

    return Built(
        params=params,
        question=(
            f"The roots of {equation} = 0 are alpha and beta. Find the "
            f"{phrase} of the roots."
        ),
        answer=n(value),
        hint=f"Give the {phrase}, as a fraction or a decimal.",
        working=(
            f"For ax^2 + bx + c = 0 the {phrase} of the roots is {rule}.",
            f"Here a = {lead}, b = {b} and c = {c}.",
            f"So the {phrase} is {n(value)}.",
        ),
    )


def _quadratic_text(a: int, b: int, c: int) -> str:
    """Write a quadratic the way it would be printed on a paper."""
    lead = "x^2" if a == 1 else f"{a}x^2"
    if b == 0:
        middle = ""
    else:
        size = "" if abs(b) == 1 else str(abs(b))
        middle = f" {'+' if b > 0 else '-'} {size}x"
    tail = "" if c == 0 else f" {'+' if c > 0 else '-'} {abs(c)}"
    return lead + middle + tail


# ------------------------------------------------------------ plane geometry


@template(
    "polygon-interior-sum",
    doc="ex-31-polygon-interior-angles",
    locator="EX 31",
    topic="Plane geometry",
    subtopic="Polygons",
)
def polygon_interior_sum(rng, params=None) -> Built:
    if params is None:
        params = {"sides": rng.randint(5, 20)}
    sides = params["sides"]
    total = (sides - 2) * 180

    return Built(
        params=params,
        question=(
            f"Find the sum of the interior angles of a polygon with {sides} sides."
        ),
        answer=n(total),
        hint="Give the sum in degrees.",
        working=(
            "The interior angles of a polygon with n sides sum to "
            "(n - 2) x 180 degrees.",
            f"With n = {sides}: ({sides} - 2) x 180 = {sides - 2} x 180.",
            f"= {total} degrees.",
        ),
    )


@template(
    "polygon-from-exterior",
    doc="ex-32-polygon-from-exterior-angle",
    locator="EX 32",
    topic="Plane geometry",
    subtopic="Polygons",
)
def polygon_from_exterior(rng, params=None) -> Built:
    if params is None:
        # Only exterior angles that divide 360 exactly describe a real regular
        # polygon, so the choice is from that list rather than a range.
        params = {"exterior": rng.choice([12, 15, 18, 20, 24, 30, 36, 40, 45, 60, 72])}
    exterior = params["exterior"]
    sides = 360 // exterior
    interior = 180 - exterior

    return Built(
        params=params,
        question=(
            f"Each exterior angle of a regular polygon is {exterior} degrees. "
            f"How many sides has the polygon?"
        ),
        answer=n(sides),
        hint="Give the number of sides.",
        working=(
            "The exterior angles of any polygon add up to 360 degrees, and in "
            "a regular polygon they are all equal.",
            f"So n = 360 / {exterior} = {sides}.",
            f"(Each interior angle is then 180 - {exterior} = {interior} "
            f"degrees.)",
        ),
    )


@template(
    "angle-at-centre",
    doc="ex-33-angle-at-centre",
    locator="EX 33",
    topic="Plane geometry",
    subtopic="Circle theorems",
)
def angle_at_centre(rng, params=None) -> Built:
    if params is None:
        params = {"circumference_angle": rng.randint(20, 80)}
    at_circumference = params["circumference_angle"]
    at_centre = 2 * at_circumference

    return Built(
        params=params,
        question=(
            f"An angle subtended at the circumference of a circle by an arc is "
            f"{at_circumference} degrees. Find the angle the same arc subtends "
            f"at the centre."
        ),
        answer=n(at_centre),
        hint="Give the angle in degrees.",
        working=(
            "The angle an arc subtends at the centre is twice the angle it "
            "subtends at the circumference.",
            f"So the angle at the centre is 2 x {at_circumference}.",
            f"= {at_centre} degrees.",
        ),
    )


@template(
    "cyclic-quadrilateral",
    doc="ex-34-cyclic-quadrilateral",
    locator="EX 34",
    topic="Plane geometry",
    subtopic="Circle theorems",
)
def cyclic_quadrilateral(rng, params=None) -> Built:
    if params is None:
        params = {"given": rng.randint(55, 125)}
    given = params["given"]
    opposite = 180 - given

    return Built(
        params=params,
        question=(
            f"PQRS is a cyclic quadrilateral in which angle PQR is {given} "
            f"degrees. Find angle PSR."
        ),
        answer=n(opposite),
        hint="Give the angle in degrees.",
        working=(
            "Opposite angles of a cyclic quadrilateral are supplementary: "
            "they add up to 180 degrees.",
            f"Angle PSR = 180 - {given}.",
            f"= {opposite} degrees.",
        ),
    )


# ---------------------------------------------------------------- mensuration


@template(
    "sector-area",
    doc="ex-35-sector-arc-and-area",
    locator="EX 35",
    topic="Mensuration",
    subtopic="Circles, arcs and sectors",
)
def sector_area(rng, params=None) -> Built:
    if params is None:
        # A radius that is a multiple of 7 cancels the 7 in 22/7, and an angle
        # that is a multiple of 45 keeps the fraction of the circle a power of
        # two -- between them the area lands on an exact decimal.
        params = {
            "radius": 7 * rng.randint(1, 5),
            "angle": rng.choice([45, 90, 135, 180, 225, 270, 315]),
        }
    radius, angle = params["radius"], params["angle"]
    area = Fraction(angle, 360) * PI * radius * radius

    return Built(
        params=params,
        question=(
            f"A sector of a circle of radius {radius} cm subtends an angle of "
            f"{angle} degrees at the centre. Find the area of the sector, "
            f"taking pi as 22/7."
        ),
        answer=n(area),
        hint="Give the area in square centimetres.",
        working=(
            "Area of a sector = (angle / 360) x pi r^2.",
            f"= ({angle}/360) x (22/7) x {radius}^2.",
            f"= {n(area)} square centimetres.",
        ),
    )


@template(
    "cone-volume",
    doc="ex-36-cone-volume-surface",
    locator="EX 36",
    topic="Mensuration",
    subtopic="Volumes and surface areas",
)
def cone_volume(rng, params=None) -> Built:
    if params is None:
        # Radius a multiple of 7 to cancel the 7 in 22/7, height a multiple of
        # 3 to cancel the third: the volume is then a whole number.
        params = {"radius": 7 * rng.randint(1, 4), "height": 3 * rng.randint(2, 8)}
    radius, height = params["radius"], params["height"]
    volume = Fraction(1, 3) * PI * radius * radius * height

    return Built(
        params=params,
        question=(
            f"A cone has base radius {radius} cm and height {height} cm. Find "
            f"its volume, taking pi as 22/7."
        ),
        answer=n(volume),
        hint="Give the volume in cubic centimetres.",
        working=(
            "Volume of a cone = (1/3) pi r^2 h.",
            f"= (1/3) x (22/7) x {radius}^2 x {height}.",
            f"= {n(volume)} cubic centimetres.",
        ),
    )


@template(
    "sphere-surface-area",
    doc="ex-37-sphere-volume-surface",
    locator="EX 37",
    topic="Mensuration",
    subtopic="Volumes and surface areas",
)
def sphere_surface_area(rng, params=None) -> Built:
    if params is None:
        params = {"radius": 7 * rng.randint(1, 5)}
    radius = params["radius"]
    area = 4 * PI * radius * radius

    return Built(
        params=params,
        question=(
            f"Find the surface area of a sphere of radius {radius} cm, taking "
            f"pi as 22/7."
        ),
        answer=n(area),
        hint="Give the area in square centimetres.",
        working=(
            "Surface area of a sphere = 4 pi r^2.",
            f"= 4 x (22/7) x {radius}^2.",
            f"= {n(area)} square centimetres.",
        ),
    )


# --------------------------------------------------------------- trigonometry


@template(
    "cosine-rule-side",
    doc="ex-40-cosine-rule",
    locator="EX 40",
    topic="Trigonometry",
    subtopic="Cosine rule",
)
def cosine_rule_side(rng, params=None) -> Built:
    if params is None:
        # 60 and 120 degrees are the two angles whose cosine is exactly a half,
        # so the squared side is a whole number and only the final root is
        # rounded.
        params = {
            "b": rng.randint(5, 14),
            "c": rng.randint(5, 14),
            "angle": rng.choice([60, 120]),
        }
    b, c, angle = params["b"], params["c"], params["angle"]

    cosine = Fraction(1, 2) if angle == 60 else Fraction(-1, 2)
    a_squared = b * b + c * c - 2 * b * c * cosine
    a = math.sqrt(float(a_squared))

    return Built(
        params=params,
        question=(
            f"In triangle ABC, b = {b} cm, c = {c} cm and angle A = {angle} "
            f"degrees. Find a, correct to one decimal place."
        ),
        answer=n(a, places=1),
        hint="Give a in centimetres, to one decimal place.",
        working=(
            "a^2 = b^2 + c^2 - 2bc cos A.",
            f"cos {angle} = {n(cosine)}, so a^2 = {b * b} + {c * c} - "
            f"2({b})({c})({n(cosine)}) = {n(a_squared)}.",
            f"a = root({n(a_squared)}) = {n(a, places=1)} cm.",
        ),
    )


@template(
    "angle-of-elevation-height",
    doc="ex-42-angle-of-elevation",
    locator="EX 42",
    topic="Trigonometry",
    subtopic="Angles of elevation",
)
def angle_of_elevation_height(rng, params=None) -> Built:
    if params is None:
        params = {
            "distance": rng.choice([20, 25, 30, 40, 50, 60, 80]),
            "angle": rng.choice([25, 30, 35, 40, 45, 50, 55, 60]),
        }
    distance, angle = params["distance"], params["angle"]
    height = distance * math.tan(math.radians(angle))

    return Built(
        params=params,
        question=(
            f"From a point {distance} m from the foot of a vertical tower, the "
            f"angle of elevation of the top of the tower is {angle} degrees. "
            f"Find the height of the tower, correct to one decimal place."
        ),
        answer=n(height, places=1),
        hint="Give the height in metres, to one decimal place.",
        working=(
            "The tower, the ground and the line of sight make a right-angled "
            "triangle, with the height opposite the angle of elevation and the "
            "distance adjacent to it.",
            f"tan {angle} = height / {distance}, so height = {distance} tan "
            f"{angle}.",
            f"= {n(height, places=1)} m.",
        ),
    )


# --------------------------------------------------------- introductory calculus


@template(
    "gradient-at-a-point",
    doc="ex-43-differentiation-turning-points",
    locator="EX 43",
    topic="Introductory calculus",
    subtopic="Differentiation",
)
def gradient_at_a_point(rng, params=None) -> Built:
    if params is None:
        params = {
            "a": rng.randint(1, 4),
            "b": rng.randint(-6, 6),
            "c": rng.randint(-8, 8),
            "d": rng.randint(-5, 5),
            "at": rng.randint(-3, 4),
        }
    a, b, c, d, at = (params[k] for k in ("a", "b", "c", "d", "at"))

    gradient = 3 * a * at * at + 2 * b * at + c
    curve = _cubic_text(a, b, c, d)

    return Built(
        params=params,
        question=(
            f"Given that y = {curve}, find dy/dx and hence the gradient of the "
            f"curve at x = {at}."
        ),
        answer=n(gradient),
        hint="Give the gradient at that point.",
        working=(
            f"Differentiate term by term: dy/dx = "
            f"{_term(3 * a, 'x^2')}{_joined(2 * b, 'x')}{_joined_constant(c)}.",
            f"At x = {at}: {3 * a}({at})^2"
            f"{_joined(2 * b, f'({at})')}{_joined_constant(c)}.",
            f"= {gradient}.",
        ),
    )


def _cubic_text(a: int, b: int, c: int, d: int) -> str:
    lead = "x^3" if a == 1 else f"{a}x^3"
    parts = [lead]
    for coefficient, power in ((b, "x^2"), (c, "x"), (d, "")):
        if coefficient == 0:
            continue
        size = "" if abs(coefficient) == 1 and power else str(abs(coefficient))
        parts.append(f"{'+' if coefficient > 0 else '-'} {size}{power}")
    return " ".join(parts)


@template(
    "definite-integral",
    doc="ex-44-definite-integral-area",
    locator="EX 44",
    topic="Introductory calculus",
    subtopic="Integration",
)
def definite_integral(rng, params=None) -> Built:
    if params is None:
        lower = rng.randint(0, 3)
        params = {
            "a": rng.randint(1, 4),
            "b": rng.randint(-5, 6),
            "lower": lower,
            "upper": lower + rng.randint(1, 4),
        }
    a, b = params["a"], params["b"]
    lower, upper = params["lower"], params["upper"]

    def antiderivative(x: int) -> Fraction:
        return Fraction(a, 3) * x**3 + Fraction(b, 2) * x**2

    value = antiderivative(upper) - antiderivative(lower)
    integrand = f"{_term(a, 'x^2')}{_joined(b, 'x')}"
    integrated = f"({a}/3)x^3" + (
        "" if b == 0 else f" {'+' if b > 0 else '-'} ({abs(b)}/2)x^2"
    )

    return Built(
        params=params,
        question=(
            f"Evaluate the integral of {integrand} with respect to x, from "
            f"x = {lower} to x = {upper}."
        ),
        answer=n(value),
        hint="Give the value, as a fraction or a decimal.",
        working=(
            f"Integrating gives {integrated}.",
            f"Evaluate at x = {upper} and subtract the value at x = {lower}.",
            f"= {n(value)}.",
        ),
    )


# --------------------------------------------------- statistics and probability


@template(
    "grouped-mean",
    doc="ex-46-grouped-mean",
    locator="EX 46",
    topic="Statistics and probability",
    subtopic="Measures of central tendency",
)
def grouped_mean(rng, params=None) -> Built:
    if params is None:
        params = {
            "start": rng.choice([1, 11, 21]),
            "width": rng.choice([10, 20]),
            "frequencies": [rng.randint(2, 12) for _ in range(5)],
        }
    start, width = params["start"], params["width"]
    frequencies = list(params["frequencies"])

    # Midpoint of a class a-b is (a + b)/2; with classes written inclusively
    # the upper bound of the first is start + width - 1.
    bounds = [
        (start + i * width, start + (i + 1) * width - 1) for i in range(len(frequencies))
    ]
    midpoints = [Fraction(lo + hi, 2) for lo, hi in bounds]

    total_frequency = sum(frequencies)
    weighted = sum(f * m for f, m in zip(frequencies, midpoints))
    mean = Fraction(weighted) / total_frequency

    table = "; ".join(
        f"{lo}-{hi}: {f}" for (lo, hi), f in zip(bounds, frequencies)
    )

    return Built(
        params=params,
        question=(
            f"The table shows the marks scored by a group of students "
            f"({table}). Calculate the mean mark, correct to two decimal "
            f"places."
        ),
        # A mean over class frequencies rarely divides exactly, and `n` shows
        # an inexact fraction as a fraction. The question asks for two
        # decimal places, so the answer is rounded to match what was asked
        # for rather than printed as 1837/40.
        answer=n(float(mean), places=2),
        hint="Give the mean, to two decimal places.",
        working=(
            "Find the midpoint of each class, multiply by its frequency, and "
            "add the products.",
            f"Sum of fx = {n(Fraction(weighted))}, and the total frequency is "
            f"{total_frequency}.",
            f"Mean = {n(Fraction(weighted))} / {total_frequency} = "
            f"{n(float(mean), places=2)}.",
        ),
    )


@template(
    "probability-without-replacement",
    doc="ex-48-probability-without-replacement",
    locator="EX 48",
    topic="Statistics and probability",
    subtopic="Probability",
)
def probability_without_replacement(rng, params=None) -> Built:
    if params is None:
        params = {"red": rng.randint(3, 8), "blue": rng.randint(3, 8)}
    red, blue = params["red"], params["blue"]
    total = red + blue

    probability = Fraction(red, total) * Fraction(red - 1, total - 1)

    return Built(
        params=params,
        question=(
            f"A bag contains {red} red balls and {blue} blue balls. Two balls "
            f"are drawn one after the other without replacement. Find the "
            f"probability that both are red."
        ),
        answer=n(probability),
        hint="Give the probability as a fraction or a decimal.",
        working=(
            f"P(first is red) = {red}/{total}.",
            f"After one red is removed, {red - 1} reds remain out of "
            f"{total - 1} balls, so P(second is red) = {red - 1}/{total - 1}.",
            f"P(both red) = ({red}/{total}) x ({red - 1}/{total - 1}) = "
            f"{n(probability)}.",
        ),
    )


# ------------------------------------------------- vectors and transformation


@template(
    "vector-magnitude",
    doc="ex-49-vectors-magnitude",
    locator="EX 49",
    topic="Vectors and transformation",
    subtopic="Vectors",
)
def vector_magnitude(rng, params=None) -> Built:
    if params is None:
        # Pythagorean triples, so the magnitude is a whole number and the
        # answer does not turn on how the student rounded a square root.
        base = rng.choice([(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25)])
        scale = rng.randint(1, 3)
        params = {
            "x": base[0] * scale * rng.choice([1, -1]),
            "y": base[1] * scale * rng.choice([1, -1]),
        }
    x, y = params["x"], params["y"]
    magnitude = math.isqrt(x * x + y * y)

    return Built(
        params=params,
        question=(
            f"A vector has components ({x}, {y}). Find its magnitude."
        ),
        answer=n(magnitude),
        hint="Give the magnitude.",
        working=(
            "The magnitude of a vector (x, y) is the square root of "
            "x^2 + y^2.",
            f"= root(({x})^2 + ({y})^2) = root({x * x} + {y * y}) = "
            f"root({x * x + y * y}).",
            f"= {magnitude}.",
        ),
    )


@template(
    "reflect-and-translate",
    doc="ex-50-transformation-of-a-point",
    locator="EX 50",
    topic="Vectors and transformation",
    subtopic="Transformations",
)
def reflect_and_translate(rng, params=None) -> Built:
    if params is None:
        params = {
            "px": rng.randint(-8, 8),
            "py": rng.randint(-8, 8),
            "hx": rng.randint(-6, 6),
            "hy": rng.randint(-6, 6),
        }
    px, py = params["px"], params["py"]
    hx, hy = params["hx"], params["hy"]

    # Reflection in the x-axis leaves x alone and changes the sign of y.
    reflected_x, reflected_y = px, -py
    image_x, image_y = reflected_x + hx, reflected_y + hy

    return Built(
        params=params,
        question=(
            f"The point P({px}, {py}) is reflected in the x-axis and the image "
            f"is then translated by the vector ({hx}, {hy}). Give the "
            f"coordinates of the final image as two numbers, x first."
        ),
        answer=f"{image_x}, {image_y}",
        # A list, not a set: (3, -4) and (-4, 3) are different points, and a
        # marker that accepted either would be teaching the wrong thing.
        answer_kind="number_list",
        hint="Give the x-coordinate and the y-coordinate, separated by a comma.",
        working=(
            f"Reflection in the x-axis sends ({px}, {py}) to "
            f"({reflected_x}, {reflected_y}).",
            f"Translating by ({hx}, {hy}) adds {hx} to the x-coordinate and "
            f"{hy} to the y-coordinate.",
            f"The image is ({image_x}, {image_y}).",
        ),
    )
