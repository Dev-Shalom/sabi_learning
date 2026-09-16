"""Schema bootstrap.

Deliberately not Alembic. The schema is created by `create_all` plus a short
list of statements that SQLAlchemy does not express (the vector extension, the
HNSW index, the trigram index). At this stage of the project a migration tool
would be ceremony: there is one deployment and the corpus is rebuilt by
re-ingesting, not by migrating. Noted in DECISIONS.md as a thing to revisit the
day there is production data worth preserving.
"""

from __future__ import annotations

from sqlalchemy import text

from sabi.config import runtime, settings
from sabi.db import engine, session_scope
from sabi.models import Base, Plan

EXTRA_DDL = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
]

POST_DDL = [
    # Cosine distance, matching the normalised vectors the embedders produce.
    """CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
       ON chunks USING hnsw (embedding vector_cosine_ops)""",
    """CREATE INDEX IF NOT EXISTS ix_answer_cache_embedding_hnsw
       ON answer_cache USING hnsw (embedding vector_cosine_ops)""",
    # Trigram index supports the fallback lexical match for queries whose terms
    # are absent from the English dictionary (variable names, "n(A)", "tan 32").
    """CREATE INDEX IF NOT EXISTS ix_chunks_text_trgm
       ON chunks USING gin (text gin_trgm_ops)""",
]


def bootstrap(seed_plans: bool = True) -> None:
    with engine().begin() as c:
        for stmt in EXTRA_DDL:
            c.execute(text(stmt))

    Base.metadata.create_all(engine())

    with engine().begin() as c:
        for stmt in POST_DDL:
            c.execute(text(stmt))

    if seed_plans:
        sync_plans()


def sync_plans() -> list[str]:
    """Push plan limits from limits.yaml into the plans table.

    The table is the source of truth at request time so an operator can change a
    cap live; this is how the file's values get there in the first place, and how
    a deliberate change in the file is applied.
    """
    cfg = runtime()
    plans = cfg.get("plans", {}) or {}
    changed: list[str] = []

    with session_scope() as s:
        for name, spec in plans.items():
            row = s.get(Plan, name)
            fields = dict(
                label=spec.get("label", name.title()),
                daily_question_cap=int(spec["daily_question_cap"]),
                daily_ip_cap=int(spec.get("daily_ip_cap", 100)),
                burst_per_minute=int(spec.get("burst_per_minute", 6)),
                monthly_cost_ceiling_usd_per_user=float(
                    spec.get("monthly_cost_ceiling_usd_per_user", 0.0)
                ),
                price_ngn_monthly=spec.get("price_ngn_monthly"),
            )
            if row is None:
                s.add(Plan(name=name, **fields))
                changed.append(f"created {name}")
            else:
                diff = [k for k, v in fields.items() if getattr(row, k) != v]
                if diff:
                    for k, v in fields.items():
                        setattr(row, k, v)
                    changed.append(f"updated {name}: {', '.join(diff)}")

        # The eval harness and CLI run as real metered users, so the plan they
        # run on has to exist. It is generous, not unlimited: the brief says no
        # request may be unmetered, including our own.
        if s.get(Plan, "internal") is None:
            s.add(
                Plan(
                    name="internal",
                    label="Internal (eval and CLI)",
                    daily_question_cap=5000,
                    daily_ip_cap=5000,
                    burst_per_minute=600,
                    monthly_cost_ceiling_usd_per_user=10.0,
                )
            )
            changed.append("created internal")

    return changed


def drop_all() -> None:
    """Used by the test fixtures only."""
    Base.metadata.drop_all(engine())


def describe() -> dict[str, object]:
    with engine().connect() as c:
        tables = [
            r[0]
            for r in c.execute(
                text(
                    "select tablename from pg_tables where schemaname='public' "
                    "order by tablename"
                )
            )
        ]
        ext = [
            r[0]
            for r in c.execute(text("select extname from pg_extension order by extname"))
        ]
    return {"database": settings().database_url.split("@")[-1], "tables": tables, "extensions": ext}
