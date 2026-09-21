"""One notion of whether two answers are the same number.

This lived in `evalharness/scorers.py`, where it only ever had to decide
whether a model's prose contained an expected value. Practice needs the same
judgement applied to something a 16-year-old typed into a box, and the moment
there are two implementations of "is 1/2 the same as 0.5" they will disagree
-- so the harness now imports from here.

The hard part is not parsing, it is deciding how forgiving to be. Too strict
and a student who wrote `0.33` for one third is told they are wrong, learns
nothing, and stops trusting the marking. Too loose and `1795` passes for
`1800`, which is worse: the product's entire claim is that it does not tell
students wrong things confidently.

The rule here is the one a human marker uses, made explicit:

    A value is accepted if it equals the true value correctly rounded to the
    precision the student actually wrote.

So `0.33` is accepted for one third, because one third to two significant
figures is 0.33. `1795` is rejected for 1800, because 1800 to four
significant figures is 1800. Nobody has to choose a tolerance, and the
tolerance is tighter for a student who claims more precision -- which is the
right direction, and the opposite of what a fixed relative tolerance does.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction

# Answers written with a minus sign U+2212, a comma thousands separator, or
# stray spacing are the same answer.
_MINUS = dict.fromkeys(map(ord, "−‒–—"), "-")

# A number as a student writes one: optional sign, digits with optional
# decimal part, optionally over a denominator, optionally in standard form.
# Also matches a bare fraction like `3/4` and a mixed number's two halves
# separately, which `parse_number` then recombines.
_NUMBER = re.compile(
    r"""
    [-+]?                      # sign
    (?:
        \d+(?:\.\d*)?          # 12, 12.5, 12.
      | \.\d+                  # .5
    )
    (?:\s*[eE]\s*[-+]?\d+)?    # standard form: 1.2e-3
    (?:\s*[/÷]\s*         # over a denominator
        \d+(?:\.\d*)?
    )?
    """,
    re.VERBOSE,
)

# Words and symbols that carry no value. Stripped before a text comparison so
# "1800 degrees" and "1800" are not judged different answers -- the question
# states the unit, so the unit is not what is being tested.
_NOISE = re.compile(
    r"(?:degrees?|deg|cm2|cm3|m2|m3|cm|mm|km|kg|sq|units?|naira|"
    r"years?|months?|days?|hours?|minutes?|seconds?)\b",
    re.IGNORECASE,
)


def normalise_value(text: str) -> str:
    """Compare answers without arguing about spacing or punctuation.

    Unchanged from the version this replaces, because the eval baseline was
    measured with it and a quiet change here would move numbers that have
    nothing to do with practice.
    """
    return re.sub(r"[\s,]+", "", text.lower()).replace("−", "-")


def _clean(text: str) -> str:
    out = str(text or "").translate(_MINUS)
    # Thousands separators only -- a comma between two numbers is a separator
    # and must survive, so only commas sitting inside a run of digits go.
    out = re.sub(r"(?<=\d),(?=\d{3}\b)", "", out)
    return out.replace("°", " ").replace("£", " ").replace("₦", " ")


def parse_number(text: str) -> Fraction | None:
    """The single number in `text`, exactly, or None if there isn't one.

    Exact because it returns a Fraction: `1/3` is one third, not
    0.3333333333333333. That matters when the comparison is a rounding
    question, since rounding 0.3333333333333333 and rounding 1/3 do not
    always agree on the last digit.
    """
    found = find_numbers(text)
    return found[0] if len(found) == 1 else None


def find_numbers(text: str) -> list[Fraction]:
    """Every number in `text`, in order, exactly."""
    cleaned = _clean(text)
    out: list[Fraction] = []
    for match in _NUMBER.finditer(cleaned):
        value = _to_fraction(match.group(0))
        if value is not None:
            out.append(value)
    return _merge_mixed(cleaned, out)


def _merge_mixed(cleaned: str, values: list[Fraction]) -> list[Fraction]:
    """Fold `2 1/2` into one number rather than two.

    Without this a mixed number reads as the pair (2, 1/2), which would make
    a two-part answer out of a single value and fail a comparison that is
    otherwise correct.
    """
    if len(values) < 2:
        return values

    spans = [m.span() for m in _NUMBER.finditer(cleaned)]
    merged: list[Fraction] = []
    i = 0
    while i < len(values):
        if (
            i + 1 < len(values)
            and "/" in cleaned[spans[i + 1][0]:spans[i + 1][1]]
            and "/" not in cleaned[spans[i][0]:spans[i][1]]
            and values[i].denominator == 1
            and not cleaned[spans[i][1]:spans[i + 1][0]].strip()
            and 0 < values[i + 1] < 1
        ):
            whole = values[i]
            part = values[i + 1]
            merged.append(whole - part if whole < 0 else whole + part)
            i += 2
            continue
        merged.append(values[i])
        i += 1
    return merged


def _to_fraction(token: str) -> Fraction | None:
    raw = re.sub(r"\s+", "", token).replace("÷", "/")
    if not raw or raw in {"-", "+"}:
        return None
    try:
        if "/" in raw:
            top, _, bottom = raw.partition("/")
            numerator = Fraction(Decimal(top))
            denominator = Fraction(Decimal(bottom))
            if denominator == 0:
                return None
            return numerator / denominator
        return Fraction(Decimal(raw))
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None


def significant_figures(text: str) -> int:
    """How much precision the student claimed by writing it that way.

    `0.33` claims two, `1800` claims four, `1.20` claims three. Trailing
    zeros before a decimal point are genuinely ambiguous in general, and are
    counted as significant here -- the strict reading, which is the safe one,
    because it means a student who writes an exact-looking integer is held to
    it.
    """
    raw = re.sub(r"\s+", "", _clean(text))
    match = _NUMBER.search(raw)
    if not match:
        return 0
    token = match.group(0)

    # A fraction is exact; it claims no rounding at all.
    if "/" in token or "÷" in token:
        return 0

    token = re.split(r"[eE]", token)[0].lstrip("+-")
    if "." in token:
        whole, _, part = token.partition(".")
        digits = (whole + part).lstrip("0")
        # 0.00450 -> leading zeros of the fractional part are placeholders.
        return len(digits) if digits else 0
    return len(token.lstrip("0")) or 0


def _round_to_sig(value: Fraction, figures: int) -> Decimal | None:
    if figures <= 0 or value == 0:
        return Decimal(0) if value == 0 else None
    with localcontext() as ctx:
        ctx.prec = max(figures + 6, 28)
        try:
            as_decimal = Decimal(value.numerator) / Decimal(value.denominator)
        except (InvalidOperation, ZeroDivisionError):
            return None
        ctx.prec = figures
        return +as_decimal


def numbers_match(expected: Fraction, given: Fraction, given_text: str) -> bool:
    """Is `given` the true value `expected`, at the precision it was written to?

    Exactness first, so 1/2 and 0.5 and 0.50 all agree without any rounding
    being involved. Then the marker's rule: round the true value to as many
    significant figures as the student wrote, and see if that is what they
    wrote.
    """
    if expected == given:
        return True

    # Rounding is only forgiven where the student signalled they were
    # rounding. A whole number written without a decimal point is a claim of
    # exactness, so `12` is not accepted for 12.4 -- without this rule the
    # significant-figure test reads "12" as two figures and lets it through,
    # which is the one direction this must never be wrong in.
    if "." not in _clean(given_text):
        return False

    figures = significant_figures(given_text)
    # An exact fraction that is not equal is simply wrong -- there is no
    # rounding to be generous about.
    if figures == 0:
        return False
    # One significant figure is not an answer, it is a guess that happens to
    # land. "2" is not accepted for 1.8.
    if figures < 2:
        return False

    a = _round_to_sig(expected, figures)
    b = _round_to_sig(given, figures)
    return a is not None and b is not None and a == b


def answers_match(expected: str, given: str, kind: str = "number") -> bool:
    """Did the student give this answer?

    `kind` says what shape the answer has, and comes from the template that
    generated the question rather than being guessed from the text:

    * `number` -- one value. The common case.
    * `number_set` -- several values whose order does not matter, like the
      two roots of a quadratic. Compared as a multiset, so a student who
      writes them the other way round is right, and one who writes the same
      root twice is not.
    * `number_list` -- several values whose order *does* matter, like the
      coordinates of a point. (3, -4) and (-4, 3) are different answers, and
      grading them the same would teach the wrong thing.
    * `text` -- anything else, compared on normalised characters. Used only
      where a value comparison would be meaningless.
    """
    expected = str(expected or "").strip()
    given = str(given or "").strip()
    if not expected or not given:
        return False

    if kind == "text":
        return _text_equal(expected, given)

    wanted = find_numbers(expected)
    got = find_numbers(given)

    if kind == "number_list":
        if len(wanted) != len(got) or not wanted:
            return False
        given_tokens = _number_tokens(given)
        return all(
            numbers_match(want, have, given_tokens[i])
            for i, (want, have) in enumerate(zip(wanted, got))
        )

    if kind == "number_set":
        if len(wanted) != len(got) or not wanted:
            return False
        # Greedy pairing is safe here: the tolerance is tight enough that a
        # given value cannot plausibly match two different expected ones.
        remaining = list(got)
        given_tokens = _number_tokens(given)
        for want in wanted:
            for i, have in enumerate(remaining):
                if numbers_match(want, have, given_tokens[i] if i < len(given_tokens) else str(have)):
                    remaining.pop(i)
                    given_tokens.pop(i)
                    break
            else:
                return False
        return True

    if len(wanted) == 1 and len(got) == 1:
        return numbers_match(wanted[0], got[0], _number_tokens(given)[0])

    # No single number on one side or the other -- an algebraic answer, or a
    # word. Fall back to characters rather than pretending to compare values.
    return _text_equal(expected, given)


def _number_tokens(text: str) -> list[str]:
    return [m.group(0) for m in _NUMBER.finditer(_clean(text))]


def _text_equal(expected: str, given: str) -> bool:
    return _text_key(expected) == _text_key(given)


def _text_key(text: str) -> str:
    stripped = _NOISE.sub("", _clean(text))
    return re.sub(r"[\s,.*]+", "", stripped.lower()).strip("=")


def contains_value(expected_value: str | None, answer_text: str) -> bool:
    """The eval harness's question: does this prose contain the right value?

    Deliberately not `answers_match`. The harness is reading a paragraph of
    working, not a single typed answer, so containment is the right test and
    a precision rule would reject an answer that shows more working than the
    expected value does.
    """
    if not expected_value:
        return False
    return normalise_value(expected_value) in normalise_value(answer_text)
