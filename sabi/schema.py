"""Schema bootstrap.

**Now Alembic.** The old note here said this would become Alembic "the day
there is production data worth preserving". Launch is the goal and the schema
is about to grow from 19 tables to a full exam catalog, so that day arrived.

`bootstrap` handles the three situations a database can be in:

* **fresh** -- nothing there; run the migrations.
* **adopt** -- tables exist but Alembic has never seen them. Every database
  built by the old `create_all` + `MIGRATIONS` path is in this state, and they
  already match the baseline revision, so they are *stamped* rather than
  upgraded. Running the baseline against them would try to create tables that
  are already there.
* **managed** -- already under Alembic; upgrade normally.

Two things stay out of Alembic deliberately, and `bootstrap` still does them:

* **The extensions** (`vector`, `pg_trgm`). They precede the schema and are a
  property of the database rather than of a schema version -- and the baseline
  cannot create a vector column or a gin_trgm index before they exist.
* **The per-scope partial HNSW indexes** from `scope_index_ddl()`. There is one
  per live `(board, subject)`, so the set changes when a subject is switched on
  in `config/limits.yaml`. That is a configuration change, not a schema
  migration; under Alembic it would mean a migration every time a subject is
  added.

`tools/schema_drift.py` stays. It catches ORM/database divergence, which is a
different failure from a missing migration, and it is what caught two real
omissions before any of this existed.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import text

from sabi.config import runtime, settings
from sabi.db import engine, session_scope
from sabi.models import Base, Plan

EXTRA_DDL = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
]

# RETIRED, and kept on purpose. Alembic owns the schema from the baseline
# revision onward; this list is no longer executed by `bootstrap`.
#
# It is not deleted because it is the written record of how the schema reached
# the state the baseline captures, and several entries carry the reasoning for
# a column that would otherwise look arbitrary -- why `chunks.subject` is
# denormalised, why `users.email_normalised` is unique only among unmerged
# rows. Deleting it would delete that.
#
# Add nothing here. New schema changes are Alembic revisions.
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
    # 010: photographs read per day, per plan. Defaults to zero, so a plan
    # that predates the column reads no photos rather than unlimited ones --
    # a new metered capability must not arrive switched on.
    """ALTER TABLE plans
       ADD COLUMN IF NOT EXISTS daily_ocr_cap integer NOT NULL DEFAULT 0""",
]

# Indexes created by raw DDL rather than by SQLAlchemy metadata, either
# because the metadata cannot express them (a partial index, a descending
# expression, an access method pgvector or pg_trgm provides) or because they
# are per-scope and generated at runtime.
#
# Alembic's autogenerate reflects them, cannot reproduce them, and therefore
# proposes DROPPING them on every single run. `alembic/env.py` imports this set
# to filter them out. Dropping a partial scope index makes an ANN walk return
# fewer rows than LIMIT asked for, silently, which is the worst failure this
# codebase knows about -- so this list is load-bearing, not housekeeping.
#
# A new raw index must be added here in the same commit that creates it.
RAW_MANAGED_INDEXES = frozenset({
    "ix_chunks_embedding_hnsw",
    "ix_chunks_scope",
    "ix_chunks_exclusion",
    "ix_chunks_text_trgm",
    "ix_chunks_tsv",
    "ix_answer_cache_scope_hash",
    "uq_feedback_request_user",
    "uq_users_email_live",
    "ix_login_attempts_email_time",
    "ix_login_attempts_ip_time",
})

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


def _alembic_config():
    """Alembic's config, pointed at this repo rather than at a cwd."""
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings().database_url)
    return cfg


def _schema_state() -> str:
    """Which of the three situations this database is in.

    * `fresh`   -- nothing here; run the migrations.
    * `adopt`   -- tables exist but Alembic has never seen them. This is every
                   database built by the old `create_all` + `MIGRATIONS` path.
                   They already match the baseline, so they are *stamped*, not
                   upgraded: running the baseline against them would try to
                   create tables that are already there.
    * `managed` -- already under Alembic; upgrade normally.
    """
    with engine().connect() as c:
        has_table = c.execute(
            text("SELECT to_regclass('public.alembic_version')")
        ).scalar_one_or_none()
        # The presence of `alembic_version` is not enough: running
        # `alembic revision --autogenerate` against a database creates the
        # table and leaves it EMPTY. Treating that as "managed" makes the next
        # bootstrap run the baseline against a populated database and try to
        # create tables that are already there. What counts is a stamped
        # revision, so the row is what is checked.
        stamped = False
        if has_table:
            stamped = (
                c.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                .scalar_one_or_none()
                is not None
            )
        if stamped:
            return "managed"
        has_tables = c.execute(
            text("SELECT to_regclass('public.documents')")
        ).scalar_one_or_none()
        return "adopt" if has_tables else "fresh"


def bootstrap(seed_plans: bool = True) -> None:
    """Bring the database to the current schema.

    Alembic owns the tables, the columns and the static indexes. Two things
    stay here, and the split is deliberate:

    * **The extensions.** They precede the schema and are a property of the
      database rather than of a schema version.
    * **The per-scope partial HNSW indexes.** There is one per live
      `(board, subject)`, so the set changes when a subject is switched on in
      `config/limits.yaml`. That is a configuration change, not a schema
      migration, and putting them under Alembic would mean a migration every
      time a subject is added.

    `MIGRATIONS` is retained but no longer executed -- see the note on it
    above. The baseline revision captures the schema it produced.
    """
    from alembic import command

    # Extensions first: the baseline creates a vector column and a gin_trgm
    # index, and neither can exist before its extension does.
    with engine().begin() as c:
        for stmt in EXTRA_DDL:
            c.execute(text(stmt))

    cfg = _alembic_config()
    state = _schema_state()
    if state == "adopt":
        # Built by the pre-Alembic path and already matching the baseline.
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")

    with engine().begin() as c:
        for stmt in DROP_DDL:
            c.execute(text(stmt))
        for stmt in scope_index_ddl():
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
                daily_ocr_cap=int(spec.get("daily_ocr_cap", 0)),
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
        internal = s.get(Plan, "internal")
        if internal is None:
            s.add(
                Plan(
                    name="internal",
                    label="Internal (eval and CLI)",
                    daily_question_cap=5000,
                    daily_ip_cap=5000,
                    burst_per_minute=600,
                    daily_ocr_cap=500,
                    monthly_cost_ceiling_usd_per_user=10.0,
                )
            )
            changed.append("created internal")
        elif internal.daily_ocr_cap == 0:
            # `internal` is created here rather than in limits.yaml, so a new
            # metered capability has to be backfilled onto it explicitly. The
            # column defaults to zero -- correct for a real plan, where an
            # unpriced capability must not arrive switched on, and wrong for
            # the one plan our own tooling runs under.
            internal.daily_ocr_cap = 500
            changed.append("updated internal: daily_ocr_cap")

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
