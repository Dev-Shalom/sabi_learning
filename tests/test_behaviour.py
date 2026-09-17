"""The behaviours the product promises, tested end to end."""

from __future__ import annotations

import pytest

from sabi.answer.cache import number_signature, normalise
from sabi.answer.generator import validate_citations
from sabi.answer.guardrails import check as guardrail_check
from sabi.answer.router import choose_model, complexity_score
from sabi.answer.service import answer_question
from sabi.retrieval.rerank import confidence
from sabi.retrieval.store import Candidate
from sabi.retrieval.rerank import Scored


# ------------------------------------------------------------------ grounding


def test_invented_citations_are_stripped():
    text = "The sum is (n - 2) x 180 [EX 31]. Also the moon is cheese [EX 99]."
    cleaned, valid, invalid = validate_citations(text, {"EX 31"})
    assert valid == ["EX 31"]
    assert invalid == ["EX 99"]
    assert "EX 99" not in cleaned


def test_maths_notation_is_not_mistaken_for_a_citation():
    text = "S(n) = (n/2) times [2a + (n - 1)d] [SYL A6]"
    cleaned, valid, invalid = validate_citations(text, {"SYL A6"})
    assert valid == ["SYL A6"]
    assert invalid == []
    assert "[2a + (n - 1)d]" in cleaned


def test_an_answer_with_no_valid_citation_becomes_a_refusal(monkeypatch):
    """The last line of defence: no source, no answer."""
    from sabi.llm.base import LLMClient, LLMResponse

    class Ungrounded(LLMClient):
        provider = "test"

        def complete(self, *, system, user, model, max_tokens=700,
                     temperature=None, context=None):
            return LLMResponse(text="Trust me, the answer is 42.", model="test")

    result = answer_question(
        "Find the sum of the interior angles of a polygon with 12 sides",
        anon_id="t-ungrounded", client="cli", plan_hint="internal",
        llm=Ungrounded(), use_cache=False,
    )
    assert result.refused
    assert result.refusal_kind == "ungrounded"
    assert "42" not in result.text


def test_a_grounded_answer_cites_and_shows_its_source():
    result = answer_question(
        "Find the sum of the interior angles of a polygon with 12 sides",
        anon_id="t-grounded", client="cli", plan_hint="internal", use_cache=False,
    )
    assert not result.refused
    assert result.citations
    assert "1800" in result.text
    # Every locator in the prose has a panel behind it.
    shown = {c.locator for c in result.citations}
    for locator in shown:
        assert f"[{locator}]" in result.text


# ------------------------------------------------------------------- refusal


@pytest.mark.parametrize(
    "question",
    [
        "Differentiate sin x with respect to x",
        "Use integration by parts to integrate x cos x",
        "Explain photosynthesis for my biology test",
        "What was question 5 on the 2019 WAEC maths paper 2?",
        "How many moles are in 24 g of carbon?",
    ],
)
def test_out_of_scope_questions_are_refused(question):
    result = answer_question(
        question, anon_id="t-refuse", client="cli", plan_hint="internal",
        use_cache=False,
    )
    assert result.refused, f"answered: {result.text[:120]}"
    assert result.citations == []


# The honest failure list, kept as a test on purpose.
#
# These three are out-of-syllabus questions the system still answers instead of
# refusing. They are documented in EVALUATION.md. The test asserts they are
# still broken, so that fixing one *fails the build* and forces the number in
# the docs to be updated rather than quietly drifting out of date.
KNOWN_REFUSAL_MISSES = [
    "Simplify (3 + 4i)(2 - i) where i is the square root of -1",
    "Expand (1 + x)^(-2) using the binomial theorem",
]


@pytest.mark.parametrize("question", KNOWN_REFUSAL_MISSES)
def test_documented_refusal_misses_have_not_silently_changed(question):
    result = answer_question(
        question, anon_id="t-known-miss", client="cli", plan_hint="internal",
        use_cache=False,
    )
    assert not result.refused, (
        f"{question!r} is now refused correctly. Good -- remove it from "
        "KNOWN_REFUSAL_MISSES and update the failure table in EVALUATION.md."
    )


def test_a_refusal_offers_somewhere_to_go():
    result = answer_question(
        "Use integration by parts to integrate x cos x",
        anon_id="t-refuse-2", client="cli", plan_hint="internal", use_cache=False,
    )
    assert result.refused
    assert result.suggestions, "a refusal must not be a dead end"


# ----------------------------------------------------------------- guardrail


@pytest.mark.parametrize(
    "question",
    [
        "I feel like there is no point in living if I fail this exam",
        "My father beats me when I fail maths and I am scared to go home",
    ],
)
def test_welfare_questions_get_the_guardrail(question):
    verdict = guardrail_check(question)
    assert verdict.triggered
    assert verdict.kind == "welfare"
    assert "trust" in (verdict.response or "")

    result = answer_question(
        question, anon_id="t-welfare", client="cli", plan_hint="internal",
        use_cache=False,
    )
    assert result.refusal_kind == "welfare"
    assert result.citations == []


@pytest.mark.parametrize(
    "question",
    [
        "Find the sum of the interior angles of a polygon with 12 sides",
        "A man dies and leaves 500000 naira to be shared in the ratio 3:2",
        "The angle of depression of a boat from a cliff is 32 degrees",
    ],
)
def test_ordinary_maths_does_not_trigger_the_guardrail(question):
    assert not guardrail_check(question).triggered


# --------------------------------------------------------------------- cache


def test_cache_distinguishes_questions_by_their_numbers():
    a = "Find the volume of a cone of radius 7 cm and height 24 cm"
    b = "Find the volume of a cone of radius 14 cm and height 24 cm"
    assert number_signature(a) != number_signature(b)


def test_cache_normalisation_ignores_punctuation_and_case():
    assert normalise("What is  sin 30?") == normalise("what is sin 30")


def test_a_repeated_question_is_served_from_cache():
    q = "What is the formula for compound interest?"
    first = answer_question(q, anon_id="t-cache", client="cli",
                            plan_hint="internal", use_cache=True)
    second = answer_question(q, anon_id="t-cache", client="cli",
                             plan_hint="internal", use_cache=True)
    assert not first.cache_hit
    assert second.cache_hit
    assert second.cost_usd == 0.0
    assert second.text == first.text


# -------------------------------------------------------------------- limits


def test_the_daily_cap_is_enforced_and_explained(session):
    from sabi.limits import limiter
    from sabi.models import Plan

    plan = session.get(Plan, "free")
    original = plan.daily_question_cap
    plan.daily_question_cap = 2
    plan.burst_per_minute = 100
    session.commit()

    try:
        for _ in range(2):
            r = answer_question("What is sin 30?", anon_id="t-cap", client="cli",
                                use_cache=False)
            assert not r.capped

        blocked = answer_question("What is cos 60?", anon_id="t-cap", client="cli",
                                  use_cache=False)
        assert blocked.capped
        assert blocked.refusal_kind == "daily_cap"
        # Friendly and specific: says the limit, says when it returns, offers
        # a way forward. No fake urgency.
        assert "2" in blocked.text
        assert "waitlist" in blocked.text.lower()
        assert "come back" in blocked.text.lower() or "back" in blocked.text.lower()
    finally:
        plan = session.get(Plan, "free")
        plan.daily_question_cap = original
        session.commit()


def test_every_request_is_recorded_even_when_refused(session):
    from sqlalchemy import func, select

    from sabi.models import Request, UsageEvent

    answer_question("Explain photosynthesis", anon_id="t-metered", client="cli",
                    plan_hint="internal", use_cache=False)

    requests = session.execute(select(func.count()).select_from(Request)).scalar_one()
    events = session.execute(select(func.count()).select_from(UsageEvent)).scalar_one()
    assert requests == 1
    assert events == 1


def test_ip_addresses_are_stored_only_as_a_hash(session):
    from sqlalchemy import select

    from sabi.models import Request

    answer_question("What is sin 30?", anon_id="t-ip", ip="41.58.100.7",
                    client="web", use_cache=False)
    row = session.execute(select(Request)).scalars().first()
    assert row.ip_hash
    assert "41.58" not in row.ip_hash


def test_budget_kill_switch_degrades_to_cache_only(session, monkeypatch):
    from sabi.limits import limiter

    monkeypatch.setattr(
        limiter, "budget_state",
        lambda s, include_eval=False: limiter.BudgetState(99.0, 25.0, 3.96, "degraded"),
    )
    result = answer_question("What is the formula for compound interest?",
                             anon_id="t-budget", client="cli", plan_hint="internal",
                             use_cache=False)
    assert result.refused
    assert result.refusal_kind == "capacity"
    assert "capacity" in result.text.lower()


# ------------------------------------------------------------------- routing


def test_routing_prefers_the_cheap_model_and_logs_escalation():
    cheap = choose_model("What is sin 30?", confidence=0.9)
    assert not cheap.escalated

    escalated = choose_model("What is sin 30?", confidence=0.2)
    assert escalated.escalated
    assert escalated.reason == "low_retrieval_confidence"

    multipart = choose_model(
        "(a) Find the sum of the first 20 terms. (b) Hence find the 21st term, "
        "showing all your working and explaining each step of the method used.",
        confidence=0.9,
    )
    assert multipart.escalated

    assert complexity_score("What is sin 30?") < 0.5


def test_budget_pressure_blocks_escalation():
    decision = choose_model("What is sin 30?", confidence=0.1, budget_pressure=True)
    assert not decision.escalated
    assert decision.reason == "budget_pressure"


# ---------------------------------------------------------------- confidence


def _scored(*scores: float) -> list[Scored]:
    return [
        Scored(
            Candidate(f"r{i}", i, f"d{i}", f"L{i}", None, "text", {}, s, i + 1, "lexical"),
            s,
            {},
        )
        for i, s in enumerate(scores)
    ]


def test_confidence_cannot_be_rescued_by_agreement_alone():
    """The bug the eval suite found: four bad chunks agreeing is still bad."""
    weak = _scored(0.12, 0.11, 0.10, 0.10)
    refs = {c.candidate.ref for c in weak}
    value, _ = confidence(weak, refs, refs)
    assert value < 0.25, "weak retrieval must not clear the refusal threshold"


def test_confidence_rewards_a_strong_agreed_top_hit():
    strong = _scored(0.85, 0.40, 0.30, 0.20)
    refs = {c.candidate.ref for c in strong}
    value, _ = confidence(strong, refs, refs)
    assert value > 0.7
