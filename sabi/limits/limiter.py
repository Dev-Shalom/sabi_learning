"""Metering, rate limiting and the budget kill switch.

Every request passes through here, including the eval harness and the CLI. The
internal plan is generous, not unlimited: an unmetered path is one that can
quietly drain the account, and the point of this module is that no such path
exists.

Limits are read from the `plans` table, never hardcoded, so a cap can be changed
live without a deploy.

Day boundaries are West Africa Time. A Nigerian student at 11pm should see the
cap reset at midnight where they are, not at 1am. WAT is UTC+1 all year with no
daylight saving, so a fixed offset is correct here and avoids depending on the
tz database being present on the host.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from sabi.config import runtime, settings
from sabi.models import Plan, Request, UsageEvent, User

WAT = timezone(timedelta(hours=1), "WAT")

# Events that consume a student's daily allowance. A cache hit costs us almost
# nothing but it is still a question asked, and pretending otherwise would let
# the cap drift away from what the student experiences.
COUNTED_EVENTS = ("question", "cache_hit", "refusal")


def hash_ip(ip: str) -> str:
    """One-way. A raw IP is never stored."""
    return hashlib.sha256((settings().ip_hash_salt + ip).encode()).hexdigest()[:48]


def wat_today() -> date:
    return datetime.now(WAT).date()


def next_reset() -> datetime:
    now = datetime.now(WAT)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def reset_phrase() -> str:
    """Plain words for the cap message, not a timestamp."""
    reset = next_reset()
    hours = max(1, round((reset - datetime.now(WAT)).total_seconds() / 3600))
    if hours <= 1:
        return "in about an hour"
    if hours >= 20:
        return "at midnight tonight"
    return f"at midnight, in about {hours} hours"


@dataclass
class LimitVerdict:
    allowed: bool
    reason: str = "ok"
    used_today: int = 0
    cap: int = 0
    remaining: int = 0
    reset_phrase: str = ""
    plan: str = "free"


@dataclass
class BudgetState:
    spend_usd: float
    ceiling_usd: float
    fraction: float
    mode: str  # normal | warn | degraded

    @property
    def cache_only(self) -> bool:
        return self.mode == "degraded"

    @property
    def cheap_only(self) -> bool:
        return self.mode in {"warn", "degraded"}


def get_or_create_user(s: Session, anon_id: str, plan_hint: str = "free") -> User:
    user = s.execute(select(User).where(User.anon_id == anon_id)).scalar_one_or_none()
    if user is None:
        # An unknown plan must not create an unmetered user.
        plan = plan_hint if s.get(Plan, plan_hint) else "free"
        user = User(anon_id=anon_id, plan=plan)
        s.add(user)
        s.flush()
    else:
        user.last_seen_at = datetime.now(timezone.utc)
    return user


def plan_for(s: Session, user: User) -> Plan:
    plan = s.get(Plan, user.plan)
    if plan is None:
        # Never fall back to "no limit". If the plan row is missing, the safest
        # behaviour is the strictest one we know about.
        plan = s.get(Plan, "free")
    if plan is None:
        raise RuntimeError("no plans are configured; run `sabi init`")
    return plan


def usage_today(s: Session, user: User) -> int:
    return int(
        s.execute(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                UsageEvent.user_id == user.id,
                UsageEvent.day == wat_today(),
                UsageEvent.event_type.in_(COUNTED_EVENTS),
            )
        ).scalar_one()
    )


def ip_usage_today(s: Session, ip_hash: str) -> int:
    return int(
        s.execute(
            select(func.count()).select_from(Request).where(
                Request.ip_hash == ip_hash,
                Request.created_at >= datetime.now(WAT).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
            )
        ).scalar_one()
    )


def burst_count(s: Session, user: User) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=1)
    return int(
        s.execute(
            select(func.count()).select_from(Request).where(
                Request.user_id == user.id, Request.created_at >= cutoff
            )
        ).scalar_one()
    )


def check(s: Session, user: User, ip_hash: str | None) -> LimitVerdict:
    plan = plan_for(s, user)
    used = usage_today(s, user)
    remaining = max(0, plan.daily_question_cap - used)

    base = LimitVerdict(
        allowed=True,
        used_today=used,
        cap=plan.daily_question_cap,
        remaining=remaining,
        reset_phrase=reset_phrase(),
        plan=plan.name,
    )

    if used >= plan.daily_question_cap:
        base.allowed = False
        base.reason = "daily_cap"
        return base

    if burst_count(s, user) >= plan.burst_per_minute:
        base.allowed = False
        base.reason = "burst"
        return base

    # The anonymous id is resettable by clearing site data, so the per-user cap
    # alone is trivially evaded. The IP cap is the backstop, set high enough to
    # survive a school computer room behind one address.
    if ip_hash and ip_usage_today(s, ip_hash) >= plan.daily_ip_cap:
        base.allowed = False
        base.reason = "ip_cap"
        return base

    return base


def month_start() -> datetime:
    now = datetime.now(WAT)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def budget_state(s: Session) -> BudgetState:
    cfg = runtime()
    ceiling = cfg.monthly_ceiling_usd
    spend = float(
        s.execute(
            select(func.coalesce(func.sum(Request.cost_usd), 0)).where(
                Request.created_at >= month_start()
            )
        ).scalar_one()
    )
    fraction = spend / ceiling if ceiling > 0 else 0.0

    if fraction >= 1.0:
        mode = "degraded"
    elif fraction >= cfg.warn_fraction:
        mode = "warn"
    else:
        mode = "normal"

    return BudgetState(round(spend, 6), ceiling, round(fraction, 4), mode)


def user_month_cost(s: Session, user: User) -> float:
    return float(
        s.execute(
            select(func.coalesce(func.sum(Request.cost_usd), 0)).where(
                Request.user_id == user.id, Request.created_at >= month_start()
            )
        ).scalar_one()
    )


def record_usage(
    s: Session,
    user: User,
    request_id,
    event_type: str,
    cost: float,
    plan_name: str,
) -> None:
    s.add(
        UsageEvent(
            user_id=user.id,
            request_id=request_id,
            day=wat_today(),
            plan=plan_name,
            event_type=event_type,
            quantity=1,
            cost_usd=cost,
            billable=True,
        )
    )


def cap_message(verdict: LimitVerdict) -> str:
    """Friendly, specific, never a dead end. No fake urgency, no hidden limit."""
    if verdict.reason == "burst":
        return (
            "That is a lot of questions very quickly. Wait about a minute and ask "
            "again. Nothing has been lost."
        )
    if verdict.reason == "ip_cap":
        return (
            "A lot of questions have come from this network today, so Sabi has "
            f"paused answering here. It starts again {verdict.reset_phrase}. If you "
            "are at school on shared wifi, this is why."
        )
    return (
        f"You have used all {verdict.cap} of your free questions for today. "
        f"They come back {verdict.reset_phrase}.\n\n"
        "Sabi is free and that limit is what keeps it free. If you need more than "
        f"{verdict.cap} a day, join the waitlist and tell me -- that is how the "
        "limit gets raised."
    )
