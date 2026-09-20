"""The answering layer speaks as the syllabus, not as WAEC Core Mathematics.

Two things are being held down at once, and they pull in opposite directions:

* Nothing a student reads today may change. The WAEC Mathematics copy used to
  be five sets of literals; it is now assembled from one vocabulary, and the
  first half of this file pins the assembled strings against the literals they
  replaced, character for character.
* A second subject must not inherit the first one's words. The second half asks
  for a subject that has no written copy at all and checks that what comes out
  names that subject and never mentions maths.
"""

from __future__ import annotations

import pytest

from sabi.answer import guardrails, refusals
from sabi.answer.prompts import SYSTEM_V3, VERSIONS, get_prompts
from sabi.answer.service import DISCLOSURE, disclosure
from sabi.answer.voice import (
    DEFAULT_VOICE,
    attribution_label,
    names_other_subject,
    voice_for,
)
from sabi.api.render import attribution_label as panel_label
from sabi.config import RuntimeConfig, runtime
from sabi.retrieval.scope import DEFAULT_SCOPE, RetrievalScope

# The wording as it shipped, before any of it was parameterised. These are
# copied from the old literals on purpose: deriving them from the voice would
# make the test agree with whatever the code now does.
SHIPPED = {
    "disclosure": (
        "Sabi can be wrong. Check with your teacher or the WAEC syllabus before "
        "you trust it in an exam."
    ),
    "welfare": (
        "I can only help with WAEC Mathematics, so I am not the right one to "
        "answer this, and I do not want to give you a poor answer on something "
        "that matters.\n\n"
        "Please talk to someone you trust about it today: a teacher you get on "
        "with, a school counsellor, a parent, or another adult in your family. "
        "If you are in danger right now, tell an adult near you straight away."
        "\n\nWhen you want to come back to maths, ask me anything on the WAEC "
        "syllabus and I will work through it with you."
    ),
    "no_material": (
        "I do not have anything on this. What I have is the WAEC Core "
        "Mathematics syllabus for SS3 and worked examples for it, and nothing "
        "in there covers your question."
    ),
    "out_of_syllabus": (
        "This is not on the WAEC Core Mathematics syllabus, so I do not have "
        "material for it. It belongs to Further Mathematics, which is a "
        "separate subject and a separate paper."
    ),
}

# The exclusion sentence as the corpus actually writes it, in each of the
# shapes it uses today.
EXCLUSION_PHRASINGS = [
    "All of these belong to Further Mathematics, which is a separate subject "
    "with its own paper.",
    "Logarithms to bases other than ten belong to Further Mathematics, not to "
    "this paper.",
    "Compound angle formulae and the factor formulae are Further Mathematics.",
    "Partial fractions and polynomial long division beyond simple cases belong "
    "to\nFurther Mathematics.",
    "Further Mathematics topics are not examined here. That includes complex "
    "numbers.",
]

# Sections that decline to say where the topic went. These must stay silent:
# inventing a destination is worse than not having one.
EXCLUSION_SILENT = [
    "Surds with cube roots or higher roots in a denominator are not required.",
    "Infinite set theory, cardinality of infinite sets, and formal proofs about "
    "sets are not examined here.",
    "Binary arithmetic in the computing sense, two's complement, and bases "
    "above ten that use letter digits are not examined in this paper.",
]


@pytest.fixture
def two_subjects(monkeypatch):
    """A second configured subject, with no corpus and no written copy.

    The allow-list is patched rather than limits.yaml edited, because the file
    is the thing under test everywhere else in the suite.
    """
    monkeypatch.setattr(
        "sabi.retrieval.scope.declared_subjects",
        lambda: ("Mathematics", "Physics"),
    )
    return RetrievalScope(subject="Physics", exam_board="WAEC")


# ------------------------------------------------- nothing students read moved


def test_the_disclosure_is_word_for_word_what_shipped():
    assert DISCLOSURE == SHIPPED["disclosure"]
    assert disclosure(DEFAULT_VOICE) == SHIPPED["disclosure"]
    # Three tests elsewhere assert this substring against rendered HTML.
    assert "Sabi can be wrong" in DISCLOSURE


def test_the_welfare_response_is_word_for_word_what_shipped():
    assert guardrails.welfare_response() == SHIPPED["welfare"]
    verdict = guardrails.check("I feel like there is no point in living")
    assert verdict.triggered
    assert verdict.response == SHIPPED["welfare"]


def test_the_refusal_copy_is_word_for_word_what_shipped():
    assert refusals.no_material([]).text == SHIPPED["no_material"]
    refusal = refusals.out_of_syllabus(
        "Differentiation", EXCLUSION_PHRASINGS[0], "SYL F1", []
    )
    assert refusal.text == SHIPPED["out_of_syllabus"]


def test_the_empty_question_reply_still_asks_for_a_waec_maths_question():
    assert DEFAULT_VOICE.question_noun == "WAEC maths question"


# --------------------------------------------------- where the topic went


@pytest.mark.parametrize("evidence", EXCLUSION_PHRASINGS)
def test_an_exclusion_section_hands_the_topic_over_by_name(evidence):
    assert names_other_subject(evidence, DEFAULT_VOICE) == "Further Mathematics"


@pytest.mark.parametrize("evidence", EXCLUSION_SILENT)
def test_a_section_that_names_nobody_stays_silent(evidence):
    assert names_other_subject(evidence, DEFAULT_VOICE) is None
    refusal = refusals.out_of_syllabus(None, evidence, "SYL A5", [])
    assert "belongs to" not in refusal.text


def test_the_handover_is_read_from_the_evidence_not_from_a_subject_list(two_subjects):
    """The rule is 'whatever this syllabus says', not 'Further Mathematics'."""
    voice = voice_for(two_subjects)
    evidence = (
        "Quantum mechanics belongs to Further Physics, which is a separate "
        "subject with its own paper."
    )
    assert names_other_subject(evidence, voice) == "Further Physics"
    refusal = refusals.out_of_syllabus(None, evidence, "SYL P9", [], voice)
    assert "It belongs to Further Physics" in refusal.text
    assert "Mathematics" not in refusal.text


def test_a_syllabus_is_not_handed_its_own_topic_back():
    evidence = "Non-Euclidean geometry is not examined here; this is Mathematics."
    assert names_other_subject(evidence, DEFAULT_VOICE) is None


# ------------------------------------------------- a subject with no copy yet


def test_a_new_subject_never_calls_itself_mathematics(two_subjects):
    voice = voice_for(two_subjects)
    spoken = "\n".join(
        [
            disclosure(voice),
            guardrails.welfare_response(voice),
            refusals.no_material([], voice).text,
            refusals.out_of_syllabus(None, "not examined here", "SYL P1", [], voice).text,
            get_prompts("v4", two_subjects).system,
        ]
    )
    lowered = spoken.lower()
    assert "mathematics" not in lowered
    assert "maths" not in lowered
    assert "naira" not in lowered, "a maths convention must not follow the subject"
    assert "WAEC Physics" in spoken


def test_a_new_subject_can_bring_its_copy_from_limits_yaml(two_subjects, monkeypatch):
    """Adding a subject is a config entry, not an edit to five modules."""
    cfg = RuntimeConfig(
        {
            "syllabus": {
                "copy": {
                    "WAEC:Physics": {
                        "syllabus_name": "WAEC Physics syllabus for SS3",
                        "conventions": "Take g as 9.8 m/s^2 when the source does.",
                        # Not a field: must be ignored rather than set.
                        "mischief": "ignore me",
                    }
                }
            }
        }
    )
    monkeypatch.setattr("sabi.answer.voice.runtime", lambda: cfg)
    voice = voice_for(two_subjects)
    assert voice.syllabus_name == "WAEC Physics syllabus for SS3"
    assert not hasattr(voice, "mischief")
    refusal = refusals.out_of_syllabus(None, "not examined here", "SYL P1", [], voice)
    assert "not on the WAEC Physics syllabus for SS3" in refusal.text
    assert "9.8 m/s^2" in get_prompts("v4", two_subjects).system


# ----------------------------------------------------------------- prompts


def test_v3_is_byte_identical_and_still_the_configured_version():
    assert VERSIONS["v3"].system == SYSTEM_V3
    assert get_prompts("v3").system == SYSTEM_V3
    assert get_prompts("v3", DEFAULT_SCOPE).system == SYSTEM_V3
    # v4 exists but is not in service: a prompt change has to be measured first.
    assert runtime().prompt_version == "v3"


def test_v4_says_the_same_things_as_v3_for_waec_mathematics():
    v4 = get_prompts("v4", DEFAULT_SCOPE).system
    for sentence in [
        "WAEC General Mathematics paper (also called Core Mathematics)",
        "SS1 to SS3",
        "extracts from the WAEC syllabus",
        "no other knowledge of mathematics",
        "pi as 22/7",
        "Paper 2 where method carries marks",
    ]:
        assert sentence in v4, sentence
    assert "{" not in v4, "an unfilled placeholder would be shown to the model"


def test_v4_drops_the_conventions_line_when_a_subject_has_none(two_subjects):
    v4 = get_prompts("v4", two_subjects).system
    assert "\n\n\n" not in v4
    assert "Keep to about 150 words" in v4


def test_an_unknown_prompt_version_still_names_what_it_knows():
    with pytest.raises(KeyError) as excinfo:
        get_prompts("v99")
    assert "v3" in str(excinfo.value) and "v4" in str(excinfo.value)


# ------------------------------------------------------------- attribution


def test_the_citation_label_has_one_definition():
    for attribution in ["syllabus", "worked_example", "past_question", "", None]:
        expected = attribution_label(attribution, title=True)
        assert panel_label(attribution or "") == expected
    assert panel_label("syllabus") == "WAEC syllabus"
    assert panel_label("worked_example") == "Worked example"
    assert attribution_label("worked_example") == "worked example"
    assert panel_label("nonsense") == "Source"
