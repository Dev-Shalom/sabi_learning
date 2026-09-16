"""Per-request structured logging.

One line per request, JSON when `SABI_LOG_JSON` is on. It carries everything
needed to answer "what happened on request X" without opening the database:
request id, latency split between retrieval and generation, tokens, cost, which
model served it, whether it was a cache hit, whether it refused and why, and the
chunk refs that were retrieved.

What it deliberately does not carry: the question text, the answer text, the
user id or anything derived from an IP. Those live in the database where access
is controlled; the log is for operations. The users are minors and a log file is
the easiest thing in a system to over-share.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from sabi.config import settings

_logger: logging.Logger | None = None


def logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    log = logging.getLogger("sabi")
    if not log.handlers:
        # stderr, so a CLI command can pipe clean JSON on stdout while still logging.
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    log.propagate = False
    _logger = log
    return log


def log_request(record: dict[str, Any]) -> None:
    if settings().log_json:
        logger().info(json.dumps(record, default=str, sort_keys=True))
    else:
        bits = " ".join(f"{k}={v}" for k, v in sorted(record.items()))
        logger().info(bits)


def build_record(
    *,
    request_id: str,
    route: str,
    model: str | None,
    latency_ms: int,
    retrieval_ms: int,
    generation_ms: int,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    cost_is_estimated: bool,
    refused: bool,
    refusal_kind: str | None,
    cache_hit: bool,
    confidence: float | None,
    retrieved_refs: list[str],
    cited_refs: list[str],
    escalated: bool,
    plan: str,
    client: str,
) -> dict[str, Any]:
    return {
        "event": "answer",
        "request_id": request_id,
        "route": route,
        "model": model,
        "escalated": escalated,
        "latency_ms": latency_ms,
        "retrieval_ms": retrieval_ms,
        "generation_ms": generation_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": round(float(cost_usd), 8),
        "cost_is_estimated": cost_is_estimated,
        "refused": refused,
        "refusal_kind": refusal_kind,
        "cache_hit": cache_hit,
        "retrieval_confidence": confidence,
        "retrieved": retrieved_refs,
        "cited": cited_refs,
        "plan": plan,
        "client": client,
    }
