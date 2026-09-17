"""The request path, end to end.

Order of operations, and why:

1. **Guardrail** -- before anything else, because it must not depend on
   retrieval or a model behaving.
2. **Metering** -- before any work that costs money. A capped request does no
   retrieval and no generation.
3. **Budget check** -- the global kill switch. Past the ceiling the system
   serves from cache only and says so, rather than silently draining the account.
4. **Cache** -- one embedding call, one vector lookup. Near-zero cost.
5. **Retrieve, route, generate** -- the expensive path, reached last.
6. **Record** -- request row, usage event, structured log. Always, including on
   failure, because an unlogged request is one nobody can explain later.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from sabi.answer import cache as answer_cache
from sabi.answer import guardrails, refusals
from sabi.answer.generator import Generated, generate
from sabi.answer.router import choose_model
from sabi.config import runtime, settings
from sabi.corpus.ingest import corpus_version
from sabi.db import session_scope
from sabi.limits import limiter
from sabi.llm.base import LLMClient, LLMUnavailable
from sabi.obs.logging import build_record, log_request
from sabi.models import Request
from sabi.retrieval.embeddings import get_embedder, tokenize
from sabi.retrieval.pipeline import RetrievalResult, retrieve

DISCLOSURE = (
    "Sabi can be wrong. Check with your teacher or the WAEC syllabus before you "
    "trust it in an exam."
)


@dataclass
class Citation:
    locator: str
    ref: str
    title: str
    source: str
    attribution: str
    heading: str | None
    text: str
    highlight: str | None = None


@dataclass
class AnswerResult:
    request_id: str
    question: str
    text: str
    refused: bool
    refusal_kind: str | None
    citations: list[Citation] = field(default_factory=list)
    disclosure: str = DISCLOSURE
    model: str | None = None
    route: str = "llm"
    cache_hit: bool = False
    escalated: bool = False
    confidence: float | None = None
    latency_ms: int = 0
    cost_usd: float = 0.0
    cost_is_estimated: bool = False
    remaining_today: int = 0
    daily_cap: int = 0
    reset_phrase: str = ""
    capped: bool = False
    suggestions: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "question": self.question,
            "answer": self.text,
            "refused": self.refused,
            "refusal_kind": self.refusal_kind,
            "citations": [c.__dict__ for c in self.citations],
            "disclosure": self.disclosure,
            "model": self.model,
            "route": self.route,
            "cache_hit": self.cache_hit,
            "escalated": self.escalated,
            "confidence": self.confidence,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "cost_is_estimated": self.cost_is_estimated,
            "remaining_today": self.remaining_today,
            "daily_cap": self.daily_cap,
            "capped": self.capped,
            "suggestions": self.suggestions,
            "error": self.error,
        }


def get_llm() -> LLMClient:
    provider = settings().llm_provider
    if provider == "anthropic":
        from sabi.llm.anthropic_client import AnthropicLLM

        return AnthropicLLM()
    from sabi.llm.offline import OfflineLLM

    return OfflineLLM()


def _highlight(chunk_text: str, answer_text: str) -> str | None:
    """The sentence in the source that the answer leans on most.

    Rendered as a pen underline in the citation panel. If nothing overlaps
    meaningfully, return None and underline nothing -- a wrong underline is
    worse than none.
    """
    from sabi.llm.offline import SENTENCE_SPLIT, _strip_context_header
    from sabi.textutil import logical_lines

    body = _strip_context_header(chunk_text)
    answer_terms = set(tokenize(answer_text))
    if not answer_terms:
        return None

    # Work on logical lines, not wrap-lines. A worked solution is one numbered
    # step per step, and running a sentence splitter over 80-column source text
    # produces spans that start mid-step and end on a bare list marker -- an
    # underline pointing at nothing. Prose lines are then split into sentences.
    units: list[str] = []
    for line in logical_lines(body):
        units.extend(x.strip() for x in SENTENCE_SPLIT.split(line) if x.strip())

    best, best_score = None, 0.0
    for sentence in units:
        terms = set(tokenize(sentence))
        # A fragment like "Part (a)" or "For a polygon with n sides:" scores a
        # perfect overlap ratio on two or three words and tells the student
        # nothing. A line has to carry some substance before it is worth
        # underlining as the source of a claim.
        if len(terms) < 5:
            continue
        score = len(terms & answer_terms) / len(terms)
        # Prefer the longer line when two match equally well: it is the one that
        # actually states the rule.
        if score > best_score or (score == best_score and best and len(sentence) > len(best)):
            best, best_score = sentence, score

    return best if best_score >= 0.5 else None


def _citations_from(retrieval: RetrievalResult, locators: list[str], answer: str) -> list[Citation]:
    """One panel per cited source.

    Sibling chunks of the same document share a locator -- the Question and the
    Solution of a worked example are two rows but one source. Showing them as
    two identical-looking panels would make the hero element of the interface
    look like a list of near-duplicates, so they are merged back into the
    document they came from, in document order.
    """
    from sabi.llm.offline import _strip_context_header
    from sabi.textutil import reflow

    out: list[Citation] = []
    for locator in dict.fromkeys(locators):
        parts = [sc.candidate for sc in retrieval.chunks if sc.candidate.locator == locator]
        if not parts:
            continue
        parts.sort(key=lambda c: c.ref)
        head = parts[0]
        prov = head.provenance
        body = reflow("\n\n".join(_strip_context_header(c.text) for c in parts))
        out.append(
            Citation(
                locator=locator,
                ref=head.ref,
                title=prov.get("title", ""),
                source=prov.get("source", ""),
                attribution=prov.get("attribution", ""),
                heading=head.heading,
                text=body,
                highlight=_highlight(body, answer),
            )
        )
    return out


def _persist(
    s: Session,
    *,
    request_id: uuid.UUID,
    user,
    plan_name: str,
    question: str,
    result: AnswerResult,
    retrieved_refs: list[str],
    cited_refs: list[str],
    tokens_in: int,
    tokens_out: int,
    retrieval_ms: int,
    generation_ms: int,
    ip_hash: str | None,
    client: str,
    event_type: str,
) -> None:
    s.add(
        Request(
            id=request_id,
            user_id=user.id,
            question=question,
            question_norm_hash=answer_cache.question_hash(question),
            answer=result.text,
            refused=result.refused,
            refusal_kind=result.refusal_kind,
            retrieved_refs=retrieved_refs,
            cited_refs=cited_refs,
            retrieval_confidence=result.confidence,
            model=result.model,
            route=result.route,
            escalated=result.escalated,
            prompt_version=runtime().prompt_version,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=result.cost_usd,
            cost_is_estimated=result.cost_is_estimated,
            latency_ms=result.latency_ms,
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
            cache_hit=result.cache_hit,
            ip_hash=ip_hash,
            client=client,
        )
    )
    limiter.record_usage(s, user, request_id, event_type, result.cost_usd, plan_name)

    log_request(
        build_record(
            request_id=str(request_id),
            route=result.route,
            model=result.model,
            latency_ms=result.latency_ms,
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=result.cost_usd,
            cost_is_estimated=result.cost_is_estimated,
            refused=result.refused,
            refusal_kind=result.refusal_kind,
            cache_hit=result.cache_hit,
            confidence=result.confidence,
            retrieved_refs=retrieved_refs,
            cited_refs=cited_refs,
            escalated=result.escalated,
            plan=plan_name,
            client=client,
        )
    )


def answer_question(
    question: str,
    anon_id: str,
    ip: str | None = None,
    client: str = "web",
    plan_hint: str = "free",
    llm: LLMClient | None = None,
    use_cache: bool = True,
) -> AnswerResult:
    """Answer one question.

    `use_cache=False` is for the eval harness: a suite that answers from the
    cache measures the cache, not the system. Cache behaviour has its own tests.
    """
    request_id = uuid.uuid4()
    started = time.perf_counter()
    question = (question or "").strip()
    ip_hash = limiter.hash_ip(ip) if ip else None
    cfg = runtime()

    with session_scope() as s:
        user = limiter.get_or_create_user(s, anon_id, plan_hint)
        plan = limiter.plan_for(s, user)

        result = AnswerResult(
            request_id=str(request_id),
            question=question,
            text="",
            refused=False,
            refusal_kind=None,
            daily_cap=plan.daily_question_cap,
        )

        if not question:
            result.text = "Ask me a WAEC maths question and I will work through it."
            result.refused = True
            result.refusal_kind = "empty"
            result.route = "refusal"
            verdict = limiter.check(s, user, ip_hash)
            result.remaining_today = verdict.remaining
            result.reset_phrase = verdict.reset_phrase
            return result

        # 1. Guardrail, before anything else.
        guard = guardrails.check(question)
        if guard.triggered:
            result.text = guard.response or ""
            result.refused = True
            result.refusal_kind = guard.kind
            result.route = "refusal"
            result.latency_ms = int((time.perf_counter() - started) * 1000)
            verdict = limiter.check(s, user, ip_hash)
            result.remaining_today = verdict.remaining
            result.reset_phrase = verdict.reset_phrase
            _persist(
                s, request_id=request_id, user=user, plan_name=plan.name,
                question=question, result=result, retrieved_refs=[], cited_refs=[],
                tokens_in=0, tokens_out=0, retrieval_ms=0, generation_ms=0,
                ip_hash=ip_hash, client=client, event_type="refusal",
            )
            return result

        # 2. Metering, before any paid work.
        verdict = limiter.check(s, user, ip_hash)
        result.remaining_today = verdict.remaining
        result.reset_phrase = verdict.reset_phrase
        if not verdict.allowed:
            result.text = limiter.cap_message(verdict)
            result.refused = True
            result.refusal_kind = verdict.reason
            result.route = "capped"
            result.capped = True
            result.latency_ms = int((time.perf_counter() - started) * 1000)
            _persist(
                s, request_id=request_id, user=user, plan_name=plan.name,
                question=question, result=result, retrieved_refs=[], cited_refs=[],
                tokens_in=0, tokens_out=0, retrieval_ms=0, generation_ms=0,
                ip_hash=ip_hash, client=client, event_type="capped",
            )
            return result

        # 3. Budget kill switch.
        budget = limiter.budget_state(s)
        version = corpus_version()

        # 4. Cache.
        embedder = get_embedder()
        query_vector = embedder.embed_one(question)
        scope = answer_cache.scope_key(cfg.prompt_version, settings().llm_provider)
        hit = (
            answer_cache.lookup(s, question, query_vector, scope, version)
            if use_cache
            else None
        )
        if hit is not None:
            answer_cache.record_hit(s, hit.entry_id)
            payload = hit.payload
            result.text = payload.get("text", "")
            result.refused = bool(payload.get("refused"))
            result.refusal_kind = payload.get("refusal_kind")
            result.citations = [Citation(**c) for c in payload.get("citations", [])]
            result.model = payload.get("model")
            result.route = "cache"
            result.cache_hit = True
            result.confidence = payload.get("confidence")
            result.suggestions = payload.get("suggestions", [])
            result.remaining_today = max(0, verdict.remaining - 1)
            result.latency_ms = int((time.perf_counter() - started) * 1000)
            _persist(
                s, request_id=request_id, user=user, plan_name=plan.name,
                question=question, result=result,
                retrieved_refs=payload.get("retrieved_refs", []),
                cited_refs=[c.ref for c in result.citations],
                tokens_in=0, tokens_out=0, retrieval_ms=0, generation_ms=0,
                ip_hash=ip_hash, client=client, event_type="cache_hit",
            )
            return result

        # Past the ceiling with no cache hit: say so. Do not degrade quietly.
        if budget.cache_only:
            r = refusals.capacity()
            result.text = r.text
            result.refused = True
            result.refusal_kind = r.kind
            result.route = "capacity"
            result.remaining_today = max(0, verdict.remaining - 1)
            result.latency_ms = int((time.perf_counter() - started) * 1000)
            _persist(
                s, request_id=request_id, user=user, plan_name=plan.name,
                question=question, result=result, retrieved_refs=[], cited_refs=[],
                tokens_in=0, tokens_out=0, retrieval_ms=0, generation_ms=0,
                ip_hash=ip_hash, client=client, event_type="refusal",
            )
            return result

        # 5. Retrieve, route, generate.
        retrieval = retrieve(s, question, version, query_vector=query_vector)
        result.confidence = retrieval.confidence

        decision = choose_model(question, retrieval.confidence, budget.cheap_only)
        result.model = decision.model
        result.escalated = decision.escalated

        gen_started = time.perf_counter()
        try:
            generated: Generated = generate(
                s, question, retrieval, llm or get_llm(), decision.model,
                query_vector=query_vector,
            )
        except LLMUnavailable as e:
            generation_ms = int((time.perf_counter() - gen_started) * 1000)
            result.text = (
                "Something went wrong reaching the model, so there is no answer "
                "this time. Your question was not used up -- try it again in a "
                "moment."
            )
            result.refused = True
            result.refusal_kind = "upstream_error"
            result.route = "error"
            result.error = str(e)
            result.latency_ms = int((time.perf_counter() - started) * 1000)
            # A failed request must not consume the student's daily allowance,
            # so it is logged as an error event and not a counted one.
            _persist(
                s, request_id=request_id, user=user, plan_name=plan.name,
                question=question, result=result,
                retrieved_refs=retrieval.refs, cited_refs=[],
                tokens_in=0, tokens_out=0, retrieval_ms=retrieval.retrieval_ms,
                generation_ms=generation_ms, ip_hash=ip_hash, client=client,
                event_type="error",
            )
            return result

        generation_ms = int((time.perf_counter() - gen_started) * 1000)

        result.text = generated.text
        result.refused = generated.refused
        result.refusal_kind = generated.refusal_kind
        result.suggestions = generated.suggestions
        result.citations = _citations_from(
            retrieval, generated.cited_locators, generated.text
        )
        result.route = "refusal" if generated.refused else "llm"

        tokens_in = generated.llm.tokens_in if generated.llm else 0
        tokens_out = generated.llm.tokens_out if generated.llm else 0
        if generated.llm:
            result.cost_usd = generated.llm.cost_usd
            result.cost_is_estimated = generated.llm.cost_is_estimated
            result.model = generated.llm.model
        else:
            # Refused before generation: routing had picked a model, but nothing
            # ran on it. Reporting the routing choice as the serving model made
            # the cost report claim Sonnet had served 903 requests for $0.
            result.model = None
            result.escalated = False

        result.remaining_today = max(0, verdict.remaining - 1)
        result.latency_ms = int((time.perf_counter() - started) * 1000)

        # A refusal is cached too: out-of-syllabus questions repeat as much as
        # answerable ones, and a fast refusal is as valuable as a fast answer.
        if use_cache:
            answer_cache.store(
                s,
                question,
                query_vector,
                {
                    "text": result.text,
                    "refused": result.refused,
                    "refusal_kind": result.refusal_kind,
                    "citations": [c.__dict__ for c in result.citations],
                    "model": result.model,
                    "confidence": result.confidence,
                    "suggestions": result.suggestions,
                    "retrieved_refs": retrieval.refs,
                },
                result.model or "unknown",
                scope,
                version,
            )

        _persist(
            s, request_id=request_id, user=user, plan_name=plan.name,
            question=question, result=result,
            retrieved_refs=retrieval.refs,
            cited_refs=[c.ref for c in result.citations],
            tokens_in=tokens_in, tokens_out=tokens_out,
            retrieval_ms=retrieval.retrieval_ms, generation_ms=generation_ms,
            ip_hash=ip_hash, client=client,
            event_type="refusal" if result.refused else "question",
        )
        return result
