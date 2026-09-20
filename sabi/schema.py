"""Schema bootstrap.

Deliberately not Alembic *yet*. The schema is created by `create_all`, plus the
statements SQLAlchemy does not express (the vector extension, the HNSW indexes,
the trigram index), plus a forward-only list of idempotent ALTERs for columns
added after a table already existed somewhere.

That last list is a migration system in miniature, and saying so is more honest
than pretending `create_all` is enough -- it silently ignores columns added to
an existing table, which is exactly the bug that made this list necessary. It
works because every statement is `IF NOT EXISTS` and the corpus is rebuilt by
re-ingesting rather than migrated. The day there is production data worth
preserving, this becomes Alembic. Noted in DECISIONS.md.
"""

from __future__ import annotations

import re

from sqlalchemy import text

from sabi.config import runtime, settings
from sabi.db import engine, session_scope
from sabi.models import Base, Plan

EXTRA_DDL = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
]

# Forward-only, idempotent, append-only. Never edit an entry, only add one.
MIGRATIONS = [
    # 001: distinguish billed spend from price-list estimates (offline provider).
    """ALTER TABLE requests
       ADD COLUMN IF NOT EXISTS cost_is_estimated boolean NOT NULL DEFAULT false""",
    # 002: cache scope keys are longer than a bare prompt version.
    "ALTER TABLE answer_cache ALTER COLUMN prompt_version TYPE varchar(64)",
    # 003: subject and board on a request, so a dashboard can break usage down
    # per subject and `promote` can carry them onto a golden item. Written from
    # the retrieval scope; defaulted for every row that predates scoping.
    """ALTER TABLE requests
       ADD COLUMN IF NOT EXISTS subject varchar(64) NOT NULL DEFAULT 'Mathematics'""",
    """ALTER TABLE requests
       ADD COLUMN IF NOT EXISTS exam_board varchar(32) NOT NULL DEFAULT 'WAEC'""",
    # 004: the same pair on a golden item, so a promoted down-vote stays in the
    # slice it came from instead of silently joining the Mathematics set.
    """ALTER TABLE golden_items
       ADD COLUMN IF NOT EXISTS subject varchar(64) NOT NULL DEFAULT 'Mathematics'""",
    """ALTER TABLE golden_items
       ADD COLUMN IF NOT EXISTS exam_board varchar(32) NOT NULL DEFAULT 'WAEC'""",
    # 005: the date a student sits the paper, for the countdown. Nullable: it is
    # volunteered, never required.
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS exam_date date",
    # 006: credentials on the existing identity row. An account is not a new
    # row -- see the User docstring -- so these are added to `users` rather
    # than living in a table of their own.
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_normalised varchar(320)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash varchar(255)",
    """ALTER TABLE users
       ADD COLUMN IF NOT EXISTS signed_up_at timestamptz""",
    """ALTER TABLE users
       ADD COLUMN IF NOT EXISTS merged_into_user_id uuid
       REFERENCES users(id) ON DELETE SET NULL""",
    # 007: the retrieval scope, denormalised onto chunks. See
    # sabi/retrieval/scope.py for why this cannot stay a join.
    """ALTER TABLE chunks
       ADD COLUMN IF NOT EXISTS subject varchar(64) NOT NULL DEFAULT 'Mathematics'""",
    """ALTER TABLE chunks
       ADD COLUMN IF NOT EXISTS exam_board varchar(32) NOT NULL DEFAULT 'WAEC'""",
    """ALTER TABLE chunks
       ADD COLUMN IF NOT EXISTS is_exclusion boolean NOT NULL DEFAULT false""",
    # 008: backfill the three above from the parent document for any rows that
    # predate them. Ingest writes them from now on, but a corpus is not
    # re-ingested just because the schema moved.
    """UPDATE chunks c
       SET subject = d.subject, exam_board = d.exam_board
       FROM documents d
       WHERE d.id = c.document_id
         AND (c.subject <> d.subject OR c.exam_board <> d.exam_board)""",
    """UPDATE chunks
       SET is_exclusion = true
       WHERE is_exclusion = false
         AND heading ILIKE '%not on this syllabus%'""",
    # 009: the cache is scoped per syllabus. Existing rows keep the default,
    # and stop matching once versions are per scope -- which is correct.
    """ALTER TABLE answer_cache
       ADD COLUMN IF NOT EXISTS scope varchar(64) NOT NULL DEFAULT 'WAEC:Mathematics'""",
]

POST_DDL = [
    # Cosine distance, matching the normalised vectors the embedders produce.
    # Kept as the unscoped fallback: it is what an unfiltered query uses, and
    # what a scoped query falls back to if its partial index is missing.
    """CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
       ON chunks USING hnsw (embedding vector_cosine_ops)""",
    # Scope columns, for the lexical and sibling paths which are not ANN and
    # so are served fine by an ordinary index.
    """CREATE INDEX IF NOT EXISTS ix_chunks_scope
       ON chunks (exam_board, subject)""",
    # The exclusion scan, which was an unindexed ILIKE over every chunk.
    """CREATE INDEX IF NOT EXISTS ix_chunks_exclusion
       ON chunks (exam_board, subject) WHERE is_exclusion""",
    # Trigram index supports the fallback lexical match for queries whose terms
    # are absent from the English dictionary (variable names, "n(A)", "tan 32").
    """CREATE INDEX IF NOT EXISTS ix_chunks_text_trgm
       ON chunks USING gin (text gin_trgm_ops)""",
    # The answer cache is looked up by scope + normalised-question hash, and
    # its vector comparison now runs over the handful of rows that survive
    # that filter. See `drop_cache_ann` below for why the ANN index went.
    """CREATE INDEX IF NOT EXISTS ix_answer_cache_scope_hash
       ON answer_cache (scope, question_norm_hash)""",
    # One vote per request per device. `/feedback` resolves the pair with
    # `scalar_one_or_none()`, so a second row there is a 500 rather than a
    # duplicate -- and merging two identities is exactly what would create one.
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_feedback_request_user
       ON feedback (request_id, user_id)""",
    # One account per address -- but only among rows that are still their own
    # identity. Partial on merged_into_user_id so that folding one identity
    # into another releases the address it was holding.
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_live
       ON users (email_normalised)
       WHERE email_normalised IS NOT NULL AND merged_into_user_id IS NULL""",
    # Throttling reads "failures for this address in the last 15 minutes" and
    # "failures from this address in the last 15 minutes" on every login.
    """CREATE INDEX IF NOT EXISTS ix_login_attempts_email_time
       ON login_attempts (email_hash, created_at DESC)""",
    """CREATE INDEX IF NOT EXISTS ix_login_attempts_ip_time
       ON login_attempts (ip_hash, created_at DESC)""",
]


def scope_index_ddl() -> list[str]:
    """One partial HNSW index per configured (board, subject) pair.

    This is the whole reason the scope predicate is a literal rather than a
    bound parameter. A single index covering every scope forces Postgres to
    post-filter the ANN walk, and the walk is bounded by `ef_search` -- so it
    runs out and returns fewer rows than `LIMIT` asked for, with no error.
    Confining the walk to one scope means `LIMIT 24` returns 24.
    """
    from sabi.retrieval.scope import live_scopes

    out: list[str] = []
    for scope in live_scopes():
        slug = re.sub(r"[^a-z0-9]+", "_", scope.key.lower()).strip("_")
        out.append(
            f"""CREATE INDEX IF NOT EXISTS ix_chunks_hnsw_{slug}
                ON chunks USING hnsw (embedding vector_cosine_ops)
                WHERE {scope.predicate('chunks')}"""
        )
    return out


# The cache's ANN index is actively harmful once the lookup is scoped: the same
# post-filter problem applies, and a cache miss there quietly removes the main
# cost lever rather than returning a wrong answer. A scope-filtered scan over a
# few thousand rows with a 256-dimension dot product is sub-millisecond.
DROP_DDL = [
    "DROP INDEX IF EXISTS ix_answer_cache_embedding_hnsw",
]


def bootstrap(seed_plans: bool = True) -> None:
    with engine().begin() as c:
        for stmt in EXTRA_DDL:
            c.execute(text(stmt))

    Base.metadata.create_all(engine())

    with engine().begin() as c:
        for stmt in MIGRATIONS:
            c.execute(text(stmt))
        for stmt in DROP_DDL:
            c.execute(text(stmt))
        for stmt in POST_DDL + scope_index_ddl():
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


# Retrieval behaviour, not just retrieval syntax, depends on this. 0.8 is where
# `hnsw.iterative_scan` arrives, which is what stops a filtered vector query
# from quietly returning fewer candidates than it asked for.
MIN_PGVECTOR = (0, 8)


def pgvector_version() -> tuple[int, ...]:
    """The installed pgvector version, as a comparable tuple."""
    with engine().connect() as c:
        raw = c.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()
    if not raw:
        return ()
    parts: list[int] = []
    for piece in str(raw).split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


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
