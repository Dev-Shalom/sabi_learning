"""Refusal text, composed from templates.

Written in the interface's own voice: plain, short, no legalese, no apology
spiral, and never implying the student asked a bad question. A refusal always
does three things -- says what is missing, says what Sabi does have, and gives
two specific things to try instead. A dead end is a product failure.
"""

from __future__ import annotations

from dataclasses import dataclass

REFUSAL_KINDS = {
    "out_of_syllabus",
    "no_material",
    "low_confidence",
    "ungrounded",
    "welfare",
    "capacity",
}


@dataclass
class Refusal:
    kind: str
    text: str
    suggestions: list[str]
    evidence_locator: str | None = None


def _suggestion_line(suggestions: list[str], lead: str = "Try asking about") -> str:
    if not suggestions:
        return ""
    if len(suggestions) == 1:
        return f'\n\n{lead} "{suggestions[0]}".'
    return f'\n\n{lead} "{suggestions[0]}" or "{suggestions[1]}".'


def out_of_syllabus(
    topic_hint: str | None, evidence_text: str, evidence_locator: str,
    suggestions: list[str],
) -> Refusal:
    """The strongest refusal: the syllabus itself says this is out of scope."""
    lead = "This is not on the WAEC Core Mathematics syllabus, so I do not have material for it."
    where = ""
    low = evidence_text.lower()
    if "further mathematics" in low:
        where = (
            " It belongs to Further Mathematics, which is a separate subject and a "
            "separate paper."
        )
    # No "you asked about X" clause, and a different lead-in for the
    # suggestions. The topic is usually still on this paper -- differentiating
    # polynomials is, differentiating sin x is not -- so "this is not on the
    # syllabus ... try asking about Differentiation" read as a contradiction.
    # Naming what the paper *does* cover makes the same two suggestions cohere.
    return Refusal(
        "out_of_syllabus",
        f"{lead}{where}"
        + _suggestion_line(suggestions, lead="On this paper you can ask about"),
        suggestions,
        evidence_locator,
    )


def no_material(suggestions: list[str]) -> Refusal:
    return Refusal(
        "no_material",
        "I do not have anything on this. What I have is the WAEC Core Mathematics "
        "syllabus for SS3 and worked examples for it, and nothing in there covers "
        "your question." + _suggestion_line(suggestions),
        suggestions,
    )


def low_confidence(suggestions: list[str]) -> Refusal:
    return Refusal(
        "low_confidence",
        "I found some material that is close to this, but not close enough to "
        "trust. I would rather tell you that than give you a method that turns "
        "out to be wrong in the exam." + _suggestion_line(suggestions),
        suggestions,
    )


def ungrounded(suggestions: list[str]) -> Refusal:
    """The answer came back without a usable citation, so it is not shown.

    This is the last line of defence and it should be rare. If it starts firing
    often, the prompt or the model is at fault and the eval suite will say so.
    """
    return Refusal(
        "ungrounded",
        "I could not put together an answer that I can show you the source for, "
        "so I am not going to show you an answer at all. Everything here has to "
        "point back at the syllabus or a worked example."
        + _suggestion_line(suggestions),
        suggestions,
    )


def capacity() -> Refusal:
    return Refusal(
        "capacity",
        "Sabi is at capacity for today. This is a free tool with a spending limit, "
        "and the limit has been reached, so new answers are paused until tomorrow. "
        "Questions that have been asked before are still answered instantly, so it "
        "is worth trying your question anyway.",
        [],
    )
