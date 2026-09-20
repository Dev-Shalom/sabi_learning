"""What Sabi is allowed to say about the syllabus it is answering under.

Every sentence in the answering layer that names a subject, an exam board or a
paper used to spell "WAEC Core Mathematics" as a literal, in five modules. That
made adding a second subject a code change in five places -- and a refusal that
says "this is not on the WAEC Core Mathematics syllabus" to a student asking a
Physics question is not a smaller bug for being a copy bug.

So the copy is derived from the `RetrievalScope` the request is being answered
under, through one `SyllabusVoice` per scope, resolved in three steps:

1. `syllabus.copy.<board>:<subject>` in limits.yaml, if it is there. This is the
   seam that makes a new subject data: drop its corpus in, list it under
   `syllabus.subjects`, and write as much or as little copy as you want.
2. The built-in table below, for scopes whose copy has been written and read by
   a human. WAEC Mathematics is there, which is why its wording is unchanged.
3. A generic derivation from the scope itself. Always correct, a little plain:
   "WAEC Physics syllabus", "a WAEC Physics question". A subject that has only
   reached step 3 still answers, still refuses, and never claims to be maths.

Nothing here is a prompt. `prompts.py` is versioned because a prompt change
moves the model's behaviour; this is the vocabulary those prompts and the
refusal templates are built from, and a scope that is not configured cannot
reach it at all (`RetrievalScope` refuses to exist first).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from sabi.config import runtime
from sabi.retrieval.scope import DEFAULT_SCOPE, RetrievalScope


@dataclass(frozen=True)
class SyllabusVoice:
    """The words for one syllabus. Frozen: it is read, never edited in place."""

    scope: RetrievalScope = DEFAULT_SCOPE

    # "the WAEC General Mathematics paper (also called Core Mathematics)"
    paper: str = ""
    # Who is reading. "SS1 to SS3".
    audience: str = "SS1 to SS3"
    # How the syllabus is referred to in passing: "WAEC syllabus".
    syllabus_short: str = ""
    # Its full name: "WAEC Core Mathematics syllabus".
    syllabus_name: str = ""
    # The field of study, lower case, mid-sentence: "mathematics".
    field_noun: str = ""
    # What a student calls it: "maths". Used where Sabi is speaking to the
    # student rather than about the syllabus.
    casual_noun: str = ""
    # What the student is invited to ask: "a WAEC maths question".
    question_noun: str = ""
    # Everything Sabi holds, for a refusal: "the WAEC Core Mathematics syllabus
    # for SS3 and worked examples for it".
    corpus_summary: str = ""
    # Subject-specific conventions for the model. Empty for a subject that has
    # not declared any -- the prompt drops the line rather than inventing one.
    conventions: str = ""
    # How working should be laid out: "the way it would be written in Paper 2
    # where method carries marks".
    working_note: str = ""

    @property
    def subject(self) -> str:
        return self.scope.subject

    @property
    def exam_board(self) -> str:
        return self.scope.exam_board

    @property
    def label(self) -> str:
        """"WAEC Mathematics". The scope's own label, never a second spelling."""
        return self.scope.label

    @property
    def key(self) -> str:
        return self.scope.key


# Copy that has been written and reviewed, keyed by scope. A scope that is not
# in here is not broken; it falls through to `_derive`. Adding an entry is
# optional polish, and limits.yaml overrides it without a deploy.
WRITTEN: dict[str, dict[str, str]] = {
    "WAEC:Mathematics": {
        "paper": (
            "WAEC General Mathematics paper (also called Core Mathematics)"
        ),
        "audience": "SS1 to SS3",
        "syllabus_short": "WAEC syllabus",
        "syllabus_name": "WAEC Core Mathematics syllabus",
        "field_noun": "mathematics",
        "casual_noun": "maths",
        "question_noun": "WAEC maths question",
        "corpus_summary": (
            "the WAEC Core Mathematics syllabus for SS3 and worked examples "
            "for it"
        ),
        "conventions": (
            "Use naira for money and the WAEC convention of taking pi as 22/7 "
            "when the source does."
        ),
        "working_note": (
            "the way it would be written in Paper 2 where method carries marks"
        ),
    },
}

# Only these keys can be set from configuration. An unknown key in limits.yaml
# is ignored rather than becoming an attribute nothing reads, and `scope` is
# not settable because it is what the lookup was keyed on.
_FIELDS = {
    "paper",
    "audience",
    "syllabus_short",
    "syllabus_name",
    "field_noun",
    "casual_noun",
    "question_noun",
    "corpus_summary",
    "conventions",
    "working_note",
}


def _derive(scope: RetrievalScope) -> dict[str, str]:
    """Copy for a subject nobody has written copy for yet.

    Plain on purpose. It names the subject and the board and claims nothing
    else -- no paper structure, no rounding convention, no year group -- because
    everything it could invent about a syllabus it has never seen would be a
    thing a student might believe.
    """
    label = scope.label
    return {
        "paper": f"{label} paper",
        "audience": "secondary school",
        "syllabus_short": f"{scope.exam_board} syllabus",
        "syllabus_name": f"{label} syllabus",
        "field_noun": scope.subject.lower(),
        "casual_noun": scope.subject.lower(),
        "question_noun": f"{label} question",
        "corpus_summary": f"the {label} syllabus and worked examples for it",
        "conventions": "",
        "working_note": "the way it would be written where method carries marks",
    }


def _configured(scope: RetrievalScope) -> dict[str, str]:
    block: Any = runtime().get(f"syllabus.copy.{scope.key}", {})
    if not isinstance(block, dict):
        return {}
    return {k: str(v) for k, v in block.items() if k in _FIELDS and v is not None}


def voice_for(scope: RetrievalScope | None = None) -> SyllabusVoice:
    """The voice for one scope. Config wins, then the written table, then derivation.

    Not cached: limits.yaml is hot-reloaded, and this is a dictionary merge on a
    path that already does a vector search.
    """
    scope = scope or DEFAULT_SCOPE
    values = _derive(scope) | WRITTEN.get(scope.key, {}) | _configured(scope)
    return SyllabusVoice(scope=scope, **values)


def voice_for_names(
    subject: str | None = None, exam_board: str | None = None
) -> SyllabusVoice:
    """Voice from raw request input, falling back rather than raising."""
    return voice_for(RetrievalScope.safe_parse(subject, exam_board))


DEFAULT_VOICE = voice_for(DEFAULT_SCOPE)


def rescope(voice: SyllabusVoice, scope: RetrievalScope) -> SyllabusVoice:
    """A copy of this voice under a different scope. Used by tests and tooling."""
    return replace(voice, scope=scope)


# --------------------------------------------------------------- attribution


ATTRIBUTION = {
    "worked_example": "worked example",
    "past_question": "past question",
}


def attribution_label(
    attribution: str | None,
    voice: SyllabusVoice | None = None,
    *,
    title: bool = False,
) -> str:
    """What a source is called, in the prompt and in the citation panel.

    One definition, two renderings: the prompt wants it mid-sentence and the
    panel wants it capitalised, so `title` capitalises rather than a second
    table drifting away from this one.
    """
    if attribution == "syllabus":
        label = (voice or DEFAULT_VOICE).syllabus_short
    else:
        label = ATTRIBUTION.get(attribution or "", "source")
    return label[:1].upper() + label[1:] if title else label


# ------------------------------------------------------- the other syllabus


# A "Not on this syllabus" section usually says where the topic *did* go, and
# the phrasing is the corpus author's, not ours:
#
#   "... belong to Further Mathematics, which is a separate subject ..."
#   "... are Further Mathematics."
#   "Further Mathematics topics are not examined here."
#
# This used to be `if "further mathematics" in text`, which is a fact about one
# subject compiled into the answering layer. Reading the name out of the
# evidence instead means a Physics syllabus that says a topic belongs to Further
# Physics gets the same sentence, with no code change -- and a section that
# names nobody still says nothing, exactly as before.
_NAME = r"[A-Z][A-Za-z]*(?:[ \n][A-Z][A-Za-z]*)*"
_ELSEWHERE = re.compile(
    rf"\bbelongs?[ \n]+to[ \n]+({_NAME})"
    rf"|\bare[ \n]+({_NAME})[ \n]*\."
    rf"|(?m:^)({_NAME}) topics are not examined",
)


def names_other_subject(
    evidence_text: str, voice: SyllabusVoice | None = None
) -> str | None:
    """The subject an exclusion section hands the topic off to, if it names one.

    Returns None when the section only says "not here", which is most of them.
    A section that names the subject it is part of is ignored: "this is not on
    the Mathematics syllabus, it belongs to Mathematics" helps nobody.
    """
    voice = voice or DEFAULT_VOICE
    for match in _ELSEWHERE.finditer(evidence_text or ""):
        name = next((g for g in match.groups() if g), "")
        name = " ".join(name.split())
        if not name or name in (voice.subject, voice.label, voice.exam_board):
            continue
        return name
    return None
