"""Practice questions built from the worked examples, with numbers resampled.

Why not just ask the 50 worked examples directly: they *are* the answer
corpus. A student handed `ex-31` as practice can paste it straight into the
composer and Sabi will retrieve the worked solution and hand it back. They
also overlap the golden eval set, so using them as practice would quietly
turn the evaluation into a memorisation test.

So each template authors the *shape* of a question, samples fresh numbers for
it, and **computes the answer in Python**. Nothing here is a typed-in answer,
which is the same discipline `tools/build_physics_examples.py` follows and for
the same reason: an answer nobody calculated is an answer nobody checked.

Every template still points at the worked example it came from, by `doc_id`
and `locator`, so a student who gets one wrong is sent to a real citation in
the corpus rather than to a generated explanation.

`tests/test_practice_templates.py` recomputes every template's answer from
scratch, sharing no code with this module. That test, not this file, is the
reason to believe the numbers.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable

# WAEC's convention, and the one the corpus uses throughout. Kept exact so
# that answers chosen to come out whole actually do.
PI = Fraction(22, 7)

# The value of g used across the Physics corpus.
G = 10


@dataclass(frozen=True)
class Built:
    """One concrete question, and everything needed to mark and explain it."""

    params: dict[str, Any]
    question: str
    answer: str
    answer_kind: str = "number"
    hint: str = ""
    working: tuple[str, ...] = ()


@dataclass(frozen=True)
class Template:
    """A question shape, tied to the worked example it was drawn from."""

    template_id: str
    source_doc_id: str
    source_locator: str
    topic: str
    subtopic: str
    make: Callable[..., Built]
    subject: str = "Mathematics"
    exam_board: str = "WAEC"

    def sample(self, rng: random.Random) -> Built:
        """A fresh variant."""
        return self.make(rng, None)

    def rebuild(self, params: dict[str, Any]) -> Built:
        """The same variant again, from stored parameters.

        This is what makes `practice_items.params` worth storing: a question
        is re-rendered from its numbers rather than from saved prose, so the
        stored row cannot drift out of step with the marking.
        """
        return self.make(None, dict(params))


_REGISTRY: dict[str, Template] = {}


def template(
    template_id: str,
    *,
    doc: str,
    locator: str,
    topic: str,
    subtopic: str,
    subject: str = "Mathematics",
    board: str = "WAEC",
):
    """Register a template.

    The decorated function takes `(rng, params)`. With `params` None it
    samples its own and computes from them; with `params` given it skips
    sampling. Sampling lives next to the arithmetic on purpose -- most of
    these constrain their numbers so the answer comes out clean, and
    splitting the two would let a constraint drift away from the working it
    protects.
    """

    def wrap(fn: Callable[..., Built]) -> Callable[..., Built]:
        if template_id in _REGISTRY:
            raise ValueError(f"duplicate template id: {template_id}")
        _REGISTRY[template_id] = Template(
            template_id=template_id,
            source_doc_id=doc,
            source_locator=locator,
            topic=topic,
            subtopic=subtopic,
            make=fn,
            subject=subject,
            exam_board=board,
        )
        return fn

    return wrap


def all_templates() -> list[Template]:
    import sabi.practice.maths  # noqa: F401  (registers on import)
    import sabi.practice.physics  # noqa: F401

    return list(_REGISTRY.values())


def get(template_id: str) -> Template | None:
    all_templates()
    return _REGISTRY.get(template_id)


def for_scope(subject: str, exam_board: str = "WAEC") -> list[Template]:
    return [
        t
        for t in all_templates()
        if t.subject == subject and t.exam_board == exam_board
    ]


def topics(subject: str, exam_board: str = "WAEC") -> list[str]:
    seen: list[str] = []
    for t in for_scope(subject, exam_board):
        if t.subtopic not in seen:
            seen.append(t.subtopic)
    return seen


# ------------------------------------------------------------------ printing


def n(value: Any, places: int = 2) -> str:
    """Write a number the way a student would.

    Whole numbers lose their `.0`, exact fractions are shown as decimals when
    they terminate and as fractions when they do not, and floats are rounded
    without trailing zeros. The point is that the answer string a template
    produces is one a student could plausibly type, because it is compared
    against what they actually typed.
    """
    if isinstance(value, Fraction):
        if value.denominator == 1:
            return str(value.numerator)
        # A fraction terminates as a decimal exactly when its denominator has
        # no prime factor other than 2 and 5.
        d = value.denominator
        while d % 2 == 0:
            d //= 2
        while d % 5 == 0:
            d //= 5
        if d == 1:
            return n(float(value), places=12)
        return f"{value.numerator}/{value.denominator}"

    if isinstance(value, int):
        return str(value)

    rounded = round(float(value), places)
    if rounded == int(rounded):
        return str(int(rounded))
    text = f"{rounded:.{places}f}".rstrip("0").rstrip(".")
    return text or "0"


def money(value: Any) -> str:
    """Naira, to the kobo only when there are kobo."""
    return n(value, places=2)
