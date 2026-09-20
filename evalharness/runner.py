"""Run the suite, aggregate, compare against a baseline, gate the build.

The harness calls `answer_question` -- the same entry point the web app uses,
through the same limiter, on the metered `internal` plan. It does not reach
inside retrieval or the generator. If it did, it would be measuring a system
that only exists inside the harness.

Caching is off for a run. A suite that answers from the cache measures the
cache.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evalharness import scorers
from evalharness.dataset import GoldenItem, load_all, summarise
from evalharness.judge import HeuristicJudge, Judge, get_judge, rubric_fingerprint

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / ".eval-runs"
BASELINE_PATH = REPO_ROOT / "eval" / "baselines" / "current.json"

# Metrics where a drop is a regression. Everything else is reported but not
# gated, because gating a metric nobody has agreed a target for just teaches
# people to pass `--force`.
GATED = {
    "retrieval.recall_at_k": 0.02,
    "retrieval.precision_at_1": 0.05,
    "citations.validity": 0.0,          # zero tolerance: this is the product claim
    "grounding.mean_ratio": 0.03,
    "correctness.value_pass_rate": 0.05,
    "refusal.unanswerable_caught": 0.05,
}
# Metrics where an *increase* is the regression.
GATED_INVERTED = {
    "refusal.over_refusal_rate": 0.05,
}


@dataclass
class ItemResult:
    slug: str
    question: str
    slice: str
    topic: str
    subject: str
    exam_board: str
    answerable: bool
    refused: bool
    refusal_kind: str | None
    answer: str
    model: str | None
    confidence: float | None
    latency_ms: int
    cost_usd: float
    cost_is_estimated: bool
    retrieval: dict[str, Any] = field(default_factory=dict)
    citations: dict[str, Any] = field(default_factory=dict)
    grounding: dict[str, Any] = field(default_factory=dict)
    value: dict[str, Any] = field(default_factory=dict)
    refusal: dict[str, Any] = field(default_factory=dict)
    verdict: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def run_item(item: GoldenItem, judge: Judge, anon_id: str) -> ItemResult:
    from sabi.answer.service import answer_question

    result = answer_question(
        question=item.question,
        anon_id=anon_id,
        ip=None,
        client="eval",
        plan_hint="internal",
        use_cache=False,
        subject=item.subject,
        exam_board=item.exam_board,
    )

    citation_locators = [c.locator for c in result.citations]
    source_texts = [c.text for c in result.citations]

    retrieval_score = scorers.score_retrieval(
        item.expected_docs, _retrieved_refs(result.request_id)
    )
    citation_score = scorers.score_citations(result.text, citation_locators)
    grounding_score = scorers.score_groundedness(result.text, source_texts)
    value_score = scorers.score_value(item.expected_value, result.text)
    refusal_score = scorers.score_refusal(
        item.answerable, item.unanswerable_kind, result.refused, result.refusal_kind
    )

    if isinstance(judge, HeuristicJudge):
        judge = HeuristicJudge(
            value_passed=value_score.passed if value_score.checked else None,
            groundedness_ratio=grounding_score.ratio,
        )

    verdict = judge.judge(
        question=item.question,
        answer=result.text,
        sources=source_texts,
        expected_answer=item.expected_answer,
        refused=result.refused,
        answerable=item.answerable,
    )

    failures: list[str] = []
    if item.answerable:
        if not retrieval_score.hit_at_k:
            failures.append("retrieval_miss")
        if refusal_score.failure_mode == "over_refused":
            failures.append("over_refused")
        if value_score.checked and not value_score.passed:
            failures.append("wrong_value")
        if not result.refused and not citation_score.has_citation:
            failures.append("no_citation")
    else:
        if refusal_score.failure_mode:
            failures.append(refusal_score.failure_mode)

    if not citation_score.all_valid:
        failures.append("invalid_citation")
    if grounding_score.ratio < 0.7 and not result.refused:
        failures.append("ungrounded")

    return ItemResult(
        slug=item.slug,
        question=item.question,
        slice=item.slice_name,
        topic=item.topic,
        subject=item.subject,
        exam_board=item.exam_board,
        answerable=item.answerable,
        refused=result.refused,
        refusal_kind=result.refusal_kind,
        answer=result.text,
        model=result.model,
        confidence=result.confidence,
        latency_ms=result.latency_ms,
        cost_usd=float(result.cost_usd),
        cost_is_estimated=result.cost_is_estimated,
        retrieval=asdict(retrieval_score),
        citations=asdict(citation_score),
        grounding=asdict(grounding_score) | {"ratio": round(grounding_score.ratio, 4)},
        value=asdict(value_score),
        refusal=asdict(refusal_score),
        verdict=verdict.to_dict(),
        failures=failures,
    )


def _retrieved_refs(request_id: str) -> list[str]:
    """Read back what retrieval actually returned for this request.

    Taken from the request row rather than passed out of the answer path,
    because the row is what an engineer would have to debug from in production.
    If the logging is wrong, the eval should notice.
    """
    from sabi.db import session_scope
    from sabi.models import Request

    with session_scope() as s:
        row = s.get(Request, uuid.UUID(request_id))
        return list(row.retrieved_refs or []) if row else []


def aggregate(results: list[ItemResult]) -> dict[str, Any]:
    answerable = [r for r in results if r.answerable]
    unanswerable = [r for r in results if not r.answerable]
    answered = [r for r in results if not r.refused]

    def rate(n: int, d: int) -> float:
        return round(n / d, 4) if d else 0.0

    value_checked = [r for r in answerable if r.value.get("checked")]
    judged_correct = [
        r for r in answered if r.verdict.get("correctness") is not None
    ]
    judged_ground = [r for r in answered if r.verdict.get("groundedness") is not None]

    metrics: dict[str, Any] = {
        "retrieval": {
            "recall_at_k": rate(
                sum(1 for r in answerable if r.retrieval["hit_at_k"]), len(answerable)
            ),
            "precision_at_1": rate(
                sum(1 for r in answerable if r.retrieval["hit_at_1"]), len(answerable)
            ),
            "mrr": round(
                sum(r.retrieval["reciprocal_rank"] for r in answerable) / len(answerable), 4
            ) if answerable else 0.0,
        },
        "citations": {
            "validity": rate(
                sum(1 for r in results if not r.citations["invalid"]), len(results)
            ),
            "answers_with_citation": rate(
                sum(1 for r in answered if r.citations["has_citation"]), len(answered)
            ),
            "invalid_total": sum(len(r.citations["invalid"]) for r in results),
        },
        "grounding": {
            "mean_ratio": round(
                sum(r.grounding["ratio"] for r in answered) / len(answered), 4
            ) if answered else 1.0,
            "fully_grounded_rate": rate(
                sum(1 for r in answered if r.grounding["ratio"] >= 0.999), len(answered)
            ),
            "unsourced_numeral_items": sum(
                1 for r in answered if r.grounding["unsourced_numerals"]
            ),
        },
        "correctness": {
            "value_pass_rate": rate(
                sum(1 for r in value_checked if r.value["passed"]), len(value_checked)
            ),
            "value_checked_n": len(value_checked),
            "judge_mean": round(
                sum(r.verdict["correctness"] for r in judged_correct) / len(judged_correct), 3
            ) if judged_correct else None,
            "judge_n": len(judged_correct),
        },
        "refusal": {
            "unanswerable_caught": rate(
                sum(1 for r in unanswerable if r.refusal["correct"]), len(unanswerable)
            ),
            "over_refusal_rate": rate(
                sum(1 for r in answerable if r.refused), len(answerable)
            ),
            "by_kind": {},
            "judge_ground_mean": round(
                sum(r.verdict["groundedness"] for r in judged_ground) / len(judged_ground), 3
            ) if judged_ground else None,
        },
        "latency_ms": scorers.aggregate([float(r.latency_ms) for r in results]),
        "cost": {
            "total_usd": round(sum(r.cost_usd for r in results), 6),
            "mean_per_question_usd": round(
                sum(r.cost_usd for r in results) / len(results), 8
            ) if results else 0.0,
            "estimated": any(r.cost_is_estimated for r in results),
        },
    }

    kinds: dict[str, list[ItemResult]] = {}
    for r in unanswerable:
        kinds.setdefault(r.slice, []).append(r)
    metrics["refusal"]["by_kind"] = {
        k: {
            "n": len(v),
            "caught": rate(sum(1 for r in v if r.refusal["correct"]), len(v)),
        }
        for k, v in sorted(kinds.items())
    }

    # Sliced per subject as well as per topic. A single global number cannot
    # show one subject regressing while another improves, and with a second
    # subject in the corpus that is the first thing this report has to be able
    # to say. Same shape as `by_topic`, so the two read the same way.
    by_subject: dict[str, dict[str, Any]] = {}
    for r in answerable:
        b = by_subject.setdefault(r.subject or "?", {"n": 0, "retrieval_hits": 0, "failures": 0})
        b["n"] += 1
        b["retrieval_hits"] += 1 if r.retrieval["hit_at_k"] else 0
        b["failures"] += 1 if r.failures else 0
    metrics["by_subject"] = {
        k: v | {"recall": rate(v["retrieval_hits"], v["n"])}
        for k, v in sorted(by_subject.items())
    }

    by_topic: dict[str, dict[str, Any]] = {}
    for r in answerable:
        b = by_topic.setdefault(r.topic or "?", {"n": 0, "retrieval_hits": 0, "failures": 0})
        b["n"] += 1
        b["retrieval_hits"] += 1 if r.retrieval["hit_at_k"] else 0
        b["failures"] += 1 if r.failures else 0
    metrics["by_topic"] = {
        k: v | {"recall": rate(v["retrieval_hits"], v["n"])}
        for k, v in sorted(by_topic.items())
    }

    return metrics


def get_metric(metrics: dict[str, Any], path: str) -> float | None:
    node: Any = metrics
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return float(node) if isinstance(node, (int, float)) else None


def run_suite(
    limit: int = 0,
    prefer_llm_judge: bool = True,
    include_promoted: bool = True,
) -> dict[str, Any]:
    from sabi.config import runtime, settings
    from sabi.corpus.ingest import corpus_version

    items = load_all(include_promoted=include_promoted)
    if limit:
        items = items[:limit]

    judge = get_judge(prefer_llm=prefer_llm_judge)
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
    anon_id = f"eval-{run_id}"

    started = time.perf_counter()
    results = [run_item(item, judge, anon_id) for item in items]
    elapsed = time.perf_counter() - started

    cfg = runtime()
    metrics = aggregate(results)
    judge_cost = round(sum(float(r.verdict.get("cost_usd") or 0) for r in results), 6)

    return {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_s": round(elapsed, 2),
        "environment": {
            "llm_provider": settings().llm_provider,
            "embedding_provider": settings().embedding_provider,
            "judge": judge.name,
            "rubric": rubric_fingerprint(),
            "prompt_version": cfg.prompt_version,
            "corpus_version": corpus_version(),
            "python": platform.python_version(),
        },
        "thresholds": {
            "refusal_threshold": cfg.refusal_threshold,
            "escalation_threshold": cfg.escalation_threshold,
            "scope_exclusion_threshold": float(
                cfg.get("retrieval.scope_exclusion_threshold", 0.42)
            ),
            "final_context_chunks": int(cfg.get("retrieval.final_context_chunks", 4)),
        },
        "dataset": summarise(items),
        "metrics": metrics,
        "judge_cost_usd": judge_cost,
        "items": [asdict(r) for r in results],
    }


def compare(run: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    """Regressions only. A metric that improved is not a build failure."""
    out: list[dict[str, Any]] = []
    for path, tolerance in GATED.items():
        now = get_metric(run["metrics"], path)
        was = get_metric(baseline.get("metrics", {}), path)
        if now is None or was is None:
            continue
        if now < was - tolerance:
            out.append(
                {"metric": path, "baseline": was, "now": now, "delta": round(now - was, 4),
                 "tolerance": tolerance}
            )
    for path, tolerance in GATED_INVERTED.items():
        now = get_metric(run["metrics"], path)
        was = get_metric(baseline.get("metrics", {}), path)
        if now is None or was is None:
            continue
        if now > was + tolerance:
            out.append(
                {"metric": path, "baseline": was, "now": now, "delta": round(now - was, 4),
                 "tolerance": tolerance, "direction": "higher is worse"}
            )
    return out


def parse_gates(spec: str) -> dict[str, float]:
    gates: dict[str, float] = {}
    for part in filter(None, (p.strip() for p in spec.split(","))):
        key, _, value = part.partition("=")
        gates[key.strip()] = float(value)
    return gates


def render(run: dict[str, Any], regressions: list[dict[str, Any]], gate_failures: list[str]) -> str:
    env = run["environment"]
    m = run["metrics"]
    ds = run["dataset"]
    lines: list[str] = []
    add = lines.append

    add(f"Sabi evaluation run {run['run_id']}")
    add(f"  provider {env['llm_provider']} / embeddings {env['embedding_provider']} "
        f"/ judge {env['judge']} (rubric {env['rubric']})")
    add(f"  prompt {env['prompt_version']}  corpus {env['corpus_version']}  "
        f"{run['duration_s']}s")
    add(f"  dataset {ds['total']} items: {ds['answerable']} answerable, "
        f"{ds['unanswerable']} unanswerable, {ds['with_value_check']} with a value check")
    if env["judge"] == "heuristic":
        add("  NOTE: heuristic judge. Correctness here means 'the expected value")
        add("        appeared in the answer', not the rubric's question.")
    add("")

    add("Retrieval")
    add(f"  recall@k         {m['retrieval']['recall_at_k']:.3f}")
    add(f"  precision@1      {m['retrieval']['precision_at_1']:.3f}")
    add(f"  MRR              {m['retrieval']['mrr']:.3f}")
    # Printed only once there is more than one subject: with a single syllabus
    # the per-subject slice is the global number restated.
    if len(m.get("by_subject") or {}) > 1:
        add("")
        add("By subject")
        for subject, v in m["by_subject"].items():
            add(f"  {subject:<20} recall {v['recall']:.3f}   "
                f"{v['failures']} failing of {v['n']}")
    add("")
    add("Citations")
    add(f"  validity         {m['citations']['validity']:.3f}  "
        f"({m['citations']['invalid_total']} invalid locators shown)")
    add(f"  answers cited    {m['citations']['answers_with_citation']:.3f}")
    add("")
    add("Groundedness")
    add(f"  mean ratio       {m['grounding']['mean_ratio']:.3f}")
    add(f"  fully grounded   {m['grounding']['fully_grounded_rate']:.3f}")
    add(f"  unsourced numerals in {m['grounding']['unsourced_numeral_items']} answers "
        "(diagnostic, not a failure)")
    add("")
    add("Correctness")
    add(f"  value pass rate  {m['correctness']['value_pass_rate']:.3f} "
        f"over {m['correctness']['value_checked_n']} checkable items")
    if m["correctness"]["judge_mean"] is not None:
        add(f"  judge mean       {m['correctness']['judge_mean']:.2f} / 2 "
            f"over {m['correctness']['judge_n']} items")
    add("")
    add("Refusal")
    add(f"  unanswerable caught  {m['refusal']['unanswerable_caught']:.3f}")
    add(f"  over-refusal rate    {m['refusal']['over_refusal_rate']:.3f}")
    for kind, v in m["refusal"]["by_kind"].items():
        add(f"    {kind:<28} {v['caught']:.3f}  (n={v['n']})")
    add("")
    add("Latency and cost")
    add(f"  p50 {m['latency_ms']['p50']:.0f} ms   p95 {m['latency_ms']['p95']:.0f} ms")
    est = " (estimated -- offline provider)" if m["cost"]["estimated"] else ""
    add(f"  ${m['cost']['mean_per_question_usd']:.6f} per question, "
        f"${m['cost']['total_usd']:.4f} total{est}")
    if run.get("judge_cost_usd"):
        add(f"  judge cost ${run['judge_cost_usd']:.4f}")
    add("")

    failing = [r for r in run["items"] if r["failures"]]
    add(f"Failures: {len(failing)} of {len(run['items'])} items")
    modes: dict[str, int] = {}
    for r in failing:
        for f in r["failures"]:
            modes[f] = modes.get(f, 0) + 1
    for mode, n in sorted(modes.items(), key=lambda kv: -kv[1]):
        add(f"  {mode:<24} {n}")
    if failing:
        add("")
        add("  worst offenders")
        for r in failing[:12]:
            add(f"    {r['slug']:<8} {','.join(r['failures']):<34} {r['question'][:52]}")

    if regressions:
        add("")
        add("REGRESSIONS against baseline")
        for r in regressions:
            add(f"  {r['metric']:<32} {r['baseline']:.3f} -> {r['now']:.3f} "
                f"({r['delta']:+.3f}, tolerance {r['tolerance']})")
    if gate_failures:
        add("")
        add("GATE FAILURES")
        for g in gate_failures:
            add(f"  {g}")

    return "\n".join(lines)


def main(args: argparse.Namespace) -> int:
    run = run_suite(
        limit=getattr(args, "limit", 0) or 0,
        prefer_llm_judge=not getattr(args, "heuristic_judge", False),
    )

    regressions: list[dict[str, Any]] = []
    # Guard the empty string: Path("") is Path("."), which exists and is a
    # directory, so a missing --baseline would try to read the repo root.
    baseline_arg = (getattr(args, "baseline", "") or "").strip()
    baseline_path = Path(baseline_arg) if baseline_arg else None
    if baseline_path and baseline_path.is_file():
        regressions = compare(run, json.loads(baseline_path.read_text(encoding="utf-8")))

    gate_failures: list[str] = []
    for key, minimum in parse_gates(getattr(args, "fail_under", "") or "").items():
        value = get_metric(run["metrics"], key)
        if value is None:
            gate_failures.append(f"{key}: not present in this run")
        elif value < minimum:
            gate_failures.append(f"{key}: {value:.4f} < required {minimum}")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(getattr(args, "save", "") or (RUNS_DIR / f"{run['run_id']}.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(run, indent=2, default=str), encoding="utf-8")

    if getattr(args, "json", False):
        print(json.dumps(run["metrics"], indent=2))
    else:
        print(render(run, regressions, gate_failures))
        print(f"\nwritten to {out_path}")

    return 1 if (regressions or gate_failures) else 0
