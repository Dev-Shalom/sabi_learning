"""Cost and latency report.

Answers the questions an operator actually asks, in this order:

1. Am I about to run out of money? (budget state, first, before anything else)
2. What does my average free user cost me per month?
3. Is it fast enough on a phone?
4. Is the cache doing its job?
5. How often does it refuse, and why?

The per-user monthly figure is the one the brief asks for and the one that is
easiest to get wrong. It is computed from observed behaviour -- spend per active
user per active day, scaled to a 30-day month -- rather than by dividing total
spend by total users, which flatters the number every time a user signs up and
leaves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text

from sabi.db import session_scope
from sabi.limits.limiter import WAT, budget_state, month_start
from sabi.models import Request, UsageEvent, User


@dataclass
class ReportData:
    days: int
    generated_at: str
    budget: dict[str, Any]
    volume: dict[str, Any]
    latency: dict[str, Any]
    cost: dict[str, Any]
    cache: dict[str, Any]
    models: list[dict[str, Any]]
    refusals: list[dict[str, Any]]
    top_users: list[dict[str, Any]]
    estimated: bool


LATENCY_SQL = text(
    """
    SELECT
      percentile_disc(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50,
      percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
      percentile_disc(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99,
      avg(latency_ms) AS mean,
      max(latency_ms) AS worst,
      percentile_disc(0.50) WITHIN GROUP (ORDER BY retrieval_ms) AS retrieval_p50,
      percentile_disc(0.50) WITHIN GROUP (ORDER BY generation_ms) AS generation_p50
    FROM requests WHERE created_at >= :since
    """
)

PER_USER_SQL = text(
    """
    WITH per_user_day AS (
      SELECT user_id, date_trunc('day', created_at) AS day,
             sum(cost_usd) AS spend, count(*) AS questions
      FROM requests
      WHERE created_at >= :since AND user_id IS NOT NULL AND client <> 'eval'
      GROUP BY user_id, date_trunc('day', created_at)
    )
    SELECT
      count(DISTINCT user_id)                       AS active_users,
      count(*)                                      AS user_days,
      COALESCE(avg(spend), 0)                       AS spend_per_active_day,
      COALESCE(avg(questions), 0)                   AS questions_per_active_day,
      COALESCE(max(spend), 0)                       AS worst_user_day
    FROM per_user_day
    """
)

TOP_USERS_SQL = text(
    """
    SELECT u.anon_id, u.plan, count(r.id) AS questions,
           sum(r.cost_usd) AS spend,
           sum(CASE WHEN r.cache_hit THEN 1 ELSE 0 END) AS cache_hits
    FROM requests r JOIN users u ON u.id = r.user_id
    WHERE r.created_at >= :since AND r.client <> 'eval'
    GROUP BY u.anon_id, u.plan
    ORDER BY spend DESC
    LIMIT :lim
    """
)


def collect(days: int = 7) -> ReportData:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    with session_scope() as s:
        budget = budget_state(s)

        total = s.execute(
            select(func.count()).select_from(Request).where(Request.created_at >= since)
        ).scalar_one()

        by_route = [
            {"route": r[0], "n": r[1], "cost": float(r[2] or 0)}
            for r in s.execute(
                select(Request.route, func.count(), func.sum(Request.cost_usd))
                .where(Request.created_at >= since)
                .group_by(Request.route)
                .order_by(func.count().desc())
            ).all()
        ]

        lat = s.execute(LATENCY_SQL, {"since": since}).one()
        per_user = s.execute(PER_USER_SQL, {"since": since}).one()

        cost_total = float(
            s.execute(
                select(func.coalesce(func.sum(Request.cost_usd), 0)).where(
                    Request.created_at >= since
                )
            ).scalar_one()
        )
        estimated = bool(
            s.execute(
                select(func.count())
                .select_from(Request)
                .where(Request.created_at >= since, Request.cost_is_estimated.is_(True))
            ).scalar_one()
        )

        # Development spend is shown separately rather than folded into the
        # student-facing figures, because a threshold sweep is thirty suite runs
        # and would otherwise dominate every per-user number in this report.
        eval_spend = float(
            s.execute(
                select(func.coalesce(func.sum(Request.cost_usd), 0)).where(
                    Request.created_at >= since, Request.client == "eval"
                )
            ).scalar_one()
        )

        cache_hits = s.execute(
            select(func.count())
            .select_from(Request)
            .where(Request.created_at >= since, Request.cache_hit.is_(True))
        ).scalar_one()

        models = [
            {
                "model": r[0] or "-",
                "n": r[1],
                "cost": float(r[2] or 0),
                "tokens_in": int(r[3] or 0),
                "tokens_out": int(r[4] or 0),
            }
            for r in s.execute(
                select(
                    Request.model,
                    func.count(),
                    func.sum(Request.cost_usd),
                    func.sum(Request.tokens_in),
                    func.sum(Request.tokens_out),
                )
                .where(Request.created_at >= since)
                .group_by(Request.model)
                .order_by(func.count().desc())
            ).all()
        ]

        refusals = [
            {"kind": r[0] or "-", "n": r[1]}
            for r in s.execute(
                select(Request.refusal_kind, func.count())
                .where(Request.created_at >= since, Request.refused.is_(True))
                .group_by(Request.refusal_kind)
                .order_by(func.count().desc())
            ).all()
        ]

        top_users = [
            {
                "anon_id": r[0][:12],
                "plan": r[1],
                "questions": r[2],
                "spend": float(r[3] or 0),
                "cache_hits": int(r[4] or 0),
            }
            for r in s.execute(TOP_USERS_SQL, {"since": since, "lim": 8}).all()
        ]

        total_users = s.execute(select(func.count()).select_from(User)).scalar_one()

    spend_per_active_day = float(per_user.spend_per_active_day or 0)
    questions_per_active_day = float(per_user.questions_per_active_day or 0)
    active_users = int(per_user.active_users or 0)
    user_days = int(per_user.user_days or 0)
    days_active_per_user = (user_days / active_users) if active_users else 0.0

    # Observed days-active scaled to a month, capped at 30. A user seen on 2 of
    # 7 days is modelled as active ~8.6 days a month, not 30.
    projected_active_days = min(30.0, days_active_per_user * (30.0 / max(days, 1)))
    monthly_per_user = spend_per_active_day * projected_active_days

    return ReportData(
        days=days,
        generated_at=datetime.now(WAT).strftime("%Y-%m-%d %H:%M WAT"),
        budget={
            "spend_mtd_usd": budget.spend_usd,
            "ceiling_usd": budget.ceiling_usd,
            "fraction": budget.fraction,
            "mode": budget.mode,
            "month_started": month_start().strftime("%Y-%m-%d"),
        },
        volume={
            "requests": int(total),
            "by_route": by_route,
            "active_users": active_users,
            "total_users": int(total_users),
            "questions_per_active_day": round(questions_per_active_day, 2),
        },
        latency={
            "p50": int(lat.p50 or 0),
            "p95": int(lat.p95 or 0),
            "p99": int(lat.p99 or 0),
            "mean": int(lat.mean or 0),
            "max": int(lat.worst or 0),
            "retrieval_p50": int(lat.retrieval_p50 or 0),
            "generation_p50": int(lat.generation_p50 or 0),
        },
        cost={
            "total_usd": round(cost_total, 6),
            "eval_usd": round(eval_spend, 6),
            "product_usd": round(cost_total - eval_spend, 6),
            "per_request_usd": round(cost_total / total, 8) if total else 0.0,
            "per_active_user_day_usd": round(spend_per_active_day, 8),
            "projected_monthly_per_user_usd": round(monthly_per_user, 6),
            "days_active_per_user_observed": round(days_active_per_user, 2),
            "worst_user_day_usd": round(float(per_user.worst_user_day or 0), 6),
        },
        cache={
            "hits": int(cache_hits),
            "hit_rate": round(cache_hits / total, 4) if total else 0.0,
        },
        models=models,
        refusals=refusals,
        top_users=top_users,
        estimated=estimated,
    )


def render_report(days: int = 7) -> str:
    d = collect(days)
    out: list[str] = []
    add = out.append

    add(f"Sabi report -- last {d.days} days, as of {d.generated_at}")
    add("")

    b = d.budget
    bar_width = 28
    filled = min(bar_width, int(b["fraction"] * bar_width))
    bar = "#" * filled + "." * (bar_width - filled)
    add(f"BUDGET  [{bar}] {b['fraction'] * 100:.1f}% of ${b['ceiling_usd']:.2f}")
    add(f"  spent this month ${b['spend_mtd_usd']:.4f}   mode: {b['mode']}")
    if b["mode"] == "degraded":
        add("  KILL SWITCH ACTIVE -- serving from cache only")
    elif b["mode"] == "warn":
        add("  past the warn line -- escalation to the stronger model is disabled")
    add("")

    add("COST")
    if d.estimated:
        add("  NOTE: some rows are price-list estimates (offline provider), not billed spend")
    add(f"  total                       ${d.cost['total_usd']:.6f}")
    add(f"    serving students          ${d.cost['product_usd']:.6f}")
    add(f"    development (eval runs)   ${d.cost['eval_usd']:.6f}  "
        "(excluded from the kill switch and the per-user figures)")
    add(f"  per request                 ${d.cost['per_request_usd']:.8f}")
    add(f"  per active user-day         ${d.cost['per_active_user_day_usd']:.8f}")
    add(f"  projected per user / month  ${d.cost['projected_monthly_per_user_usd']:.6f}")
    add(f"    (users were active on {d.cost['days_active_per_user_observed']:.2f} "
        f"of the last {d.days} days on average)")
    add(f"  worst single user-day       ${d.cost['worst_user_day_usd']:.6f}")
    add("")

    add("LATENCY (ms)")
    add(f"  p50 {d.latency['p50']}   p95 {d.latency['p95']}   p99 {d.latency['p99']}   "
        f"max {d.latency['max']}")
    add(f"  retrieval p50 {d.latency['retrieval_p50']}   "
        f"generation p50 {d.latency['generation_p50']}")
    add("")

    add("VOLUME")
    add(f"  {d.volume['requests']} requests from {d.volume['active_users']} active users "
        f"({d.volume['total_users']} known)")
    add(f"  {d.volume['questions_per_active_day']} questions per active user-day")
    for r in d.volume["by_route"]:
        add(f"    {r['route']:<10} {r['n']:>6}   ${r['cost']:.6f}")
    add("")

    add(f"CACHE  {d.cache['hits']} hits, {d.cache['hit_rate'] * 100:.1f}% of requests")
    add("")

    add("MODELS")
    for m in d.models:
        add(f"  {m['model']:<24} {m['n']:>6}  ${m['cost']:.6f}  "
            f"in {m['tokens_in']:>8}  out {m['tokens_out']:>7}")
    add("")

    if d.refusals:
        add("REFUSALS")
        for r in d.refusals:
            add(f"  {r['kind']:<20} {r['n']:>6}")
        add("")

    if d.top_users:
        add("MOST EXPENSIVE USERS")
        add(f"  {'anon id':<14} {'plan':<10} {'questions':>9} {'cache':>6} {'spend':>12}")
        for u in d.top_users:
            add(f"  {u['anon_id']:<14} {u['plan']:<10} {u['questions']:>9} "
                f"{u['cache_hits']:>6} ${u['spend']:>11.6f}")

    return "\n".join(out)
