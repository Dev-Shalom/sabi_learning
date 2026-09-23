"""Alembic, and the three states a database can be in.

The acceptance criterion for adopting Alembic was that migrations upgrade and
downgrade cleanly. That is checked here against a scratch database of its own,
because a downgrade drops every table and running it against the shared test
database would destroy the corpus every other test depends on.

The state detection is worth its own tests for a specific reason: running
`alembic revision --autogenerate` creates `alembic_version` and leaves it
empty. A check that only asks whether the table exists then reports a
pre-Alembic database as managed, runs the baseline against it, and tries to
create tables that are already there. That happened once, on the real
development database, and this is what stops it happening again.
"""

from __future__ import annotations

import os

import psycopg
import pytest
from sqlalchemy import text

SCRATCH = "sabi_migration_test"
ADMIN = os.environ.get(
    "SABI_TEST_ADMIN_URL", "postgresql://sabi:sabi@localhost:5433/postgres"
)
SCRATCH_URL = f"postgresql+psycopg://sabi:sabi@localhost:5433/{SCRATCH}"


def _recreate_scratch() -> None:
    with psycopg.connect(ADMIN, autocommit=True, connect_timeout=15) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (SCRATCH,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{SCRATCH}"')
        conn.execute(f'CREATE DATABASE "{SCRATCH}"')
    with psycopg.connect(
        ADMIN.replace("/postgres", f"/{SCRATCH}"), autocommit=True
    ) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def _drop_scratch() -> None:
    with psycopg.connect(ADMIN, autocommit=True, connect_timeout=15) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (SCRATCH,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{SCRATCH}"')


@pytest.fixture
def scratch(monkeypatch):
    """A database of this test's own, torn down afterwards.

    `sabi.db.engine` is cached, so the environment variable alone is not
    enough -- the cache is cleared on the way in and on the way out, or every
    later test in the session would talk to a database that no longer exists.
    """
    from sabi import db
    from sabi.config import settings

    def _reset() -> None:
        # `settings` is an lru_cache; the engine and session factory are
        # module-level globals. All three have to be cleared together, or the
        # next caller keeps a connection pool pointed at a database that is
        # about to stop existing.
        settings.cache_clear()
        if db._engine is not None:
            db._engine.dispose()
        db._engine = None
        db._Session = None

    original = os.environ.get("SABI_DATABASE_URL")
    _recreate_scratch()
    monkeypatch.setenv("SABI_DATABASE_URL", SCRATCH_URL)
    _reset()
    try:
        yield SCRATCH_URL
    finally:
        if original is not None:
            os.environ["SABI_DATABASE_URL"] = original
        _reset()
        _drop_scratch()


# ------------------------------------------------------------------ the point


def test_migrations_upgrade_and_downgrade_cleanly(scratch):
    """The acceptance criterion for adopting Alembic, run for real."""
    from alembic import command

    from sabi.db import engine
    from sabi.schema import _alembic_config

    cfg = _alembic_config()

    command.upgrade(cfg, "head")
    with engine().connect() as c:
        tables = set(
            r[0]
            for r in c.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
        )
    assert "documents" in tables and "chunks" in tables and "practice_sets" in tables
    assert "alembic_version" in tables

    command.downgrade(cfg, "base")
    with engine().connect() as c:
        left = set(
            r[0]
            for r in c.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
        )
    assert left == {"alembic_version"}, (
        f"downgrade left tables behind: {sorted(left - {'alembic_version'})}"
    )

    # And it comes back. A downgrade that cannot be re-upgraded is a one-way
    # door with a handle painted on it.
    command.upgrade(cfg, "head")
    with engine().connect() as c:
        again = set(
            r[0]
            for r in c.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
        )
    assert again == tables


def test_the_raw_indexes_survive_the_round_trip(scratch):
    """The indexes SQLAlchemy's metadata cannot express.

    A partial index, an index on a descending expression, and the two access
    methods pgvector and pg_trgm provide. Autogenerate proposes dropping all of
    them, which is why `include_object` filters them and why the baseline
    creates them with raw DDL.
    """
    from alembic import command

    from sabi.db import engine
    from sabi.schema import _alembic_config

    command.upgrade(_alembic_config(), "head")
    with engine().connect() as c:
        names = {
            r[0]
            for r in c.execute(
                text("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
            )
        }

    for required in (
        "ix_chunks_embedding_hnsw",
        "ix_chunks_exclusion",
        "ix_chunks_text_trgm",
        "uq_users_email_live",
        "uq_feedback_request_user",
        "ix_login_attempts_email_time",
    ):
        assert required in names, f"{required} did not survive the migration"


# -------------------------------------------------------- adopting a database


def test_an_empty_database_is_fresh(scratch):
    from sabi.schema import _schema_state

    assert _schema_state() == "fresh"


def test_a_database_built_the_old_way_is_adopted_not_rebuilt(scratch):
    """The state every pre-Alembic database is in.

    It already matches the baseline, so it is stamped. Running the baseline
    against it would try to create tables that are already there.
    """
    from sabi.db import engine
    from sabi.schema import _schema_state, bootstrap

    # Build it the way `create_all` would have, with no Alembic anywhere.
    from sabi.models import Base

    Base.metadata.create_all(engine())
    assert _schema_state() == "adopt"

    bootstrap(seed_plans=False)
    assert _schema_state() == "managed"

    with engine().connect() as c:
        stamped = c.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert stamped


def test_an_empty_alembic_version_table_is_not_managed(scratch):
    """The bug this cost an hour of confusion to find.

    `alembic revision --autogenerate` creates `alembic_version` and leaves it
    empty. Reading the table's existence as "managed" made bootstrap run the
    baseline against a fully populated database.
    """
    from sabi.db import engine
    from sabi.models import Base
    from sabi.schema import _schema_state

    Base.metadata.create_all(engine())
    with engine().begin() as c:
        c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) NOT NULL)"
            )
        )

    assert _schema_state() == "adopt", (
        "an empty alembic_version was read as a stamped database"
    )


def test_bootstrap_is_idempotent(scratch):
    from sabi.schema import _schema_state, bootstrap

    bootstrap(seed_plans=False)
    bootstrap(seed_plans=False)
    bootstrap(seed_plans=False)
    assert _schema_state() == "managed"


# ------------------------------------------------------------ the old list


def test_the_retired_migration_list_is_no_longer_executed():
    """`MIGRATIONS` is kept for its reasoning, not for its effect.

    Every entry is `IF NOT EXISTS`, so running it would be harmless and
    invisible -- which is exactly why this is asserted rather than assumed.
    """
    import ast
    import inspect
    import textwrap

    from sabi import schema

    # Parse rather than string-match: the docstring names the list in order to
    # explain why it is retired, so a substring search over the raw source
    # finds it and proves nothing.
    tree = ast.parse(textwrap.dedent(inspect.getsource(schema.bootstrap)))
    fn = tree.body[0]
    statements = fn.body
    if (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and isinstance(statements[0].value.value, str)
    ):
        statements = statements[1:]

    names = {
        n.id for s in statements for n in ast.walk(ast.Module(body=[s], type_ignores=[]))
        if isinstance(n, ast.Name)
    }
    assert "MIGRATIONS" not in names, (
        "bootstrap executes the retired MIGRATIONS list again"
    )
    assert schema.MIGRATIONS, "the list itself should be kept for its comments"


def test_there_is_exactly_one_migration_head():
    """Two heads mean two people added a revision without rebasing."""
    from alembic.script import ScriptDirectory

    from sabi.schema import _alembic_config

    heads = ScriptDirectory.from_config(_alembic_config()).get_heads()
    assert len(heads) == 1, f"migration history has branched: {heads}"
