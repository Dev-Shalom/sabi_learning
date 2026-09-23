"""Alembic environment.

Two things here are deliberate and would otherwise bite.

**The URL comes from the application's settings, never from alembic.ini.**
There is one source of truth for where the database is, and it is
`SABI_DATABASE_URL`. A connection string duplicated in an ini file drifts, and
the first symptom is a migration applied to the wrong database.

**pgvector's types must be importable when autogenerate runs.** `Vector` is a
third-party type; without importing `pgvector.sqlalchemy` here, autogenerate
either fails or -- worse -- decides the embedding columns need dropping.
`render_item` below makes it emit a real `Vector(n)` rather than the repr of
an object nobody can import.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Imported for its side effect: registering the vector type before any
# reflection or comparison happens.
import pgvector.sqlalchemy  # noqa: F401

from sabi.config import settings
from sabi.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings().database_url)

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Emit `Vector(dim)` in generated migrations instead of an opaque repr."""
    # The class is VECTOR, not Vector -- matching the wrong spelling is why
    # the first baseline emitted an unimportable full path and failed to run.
    if type_ == "type" and obj.__class__.__name__.upper() == "VECTOR":
        autogen_context.imports.add("from pgvector.sqlalchemy import Vector")
        dim = getattr(obj, "dim", None)
        return f"Vector({dim})" if dim else "Vector()"
    return False


def include_object(obj, name, type_, reflected, compare_to):
    """Keep autogenerate away from what it cannot see properly.

    The HNSW and trigram indexes are created by raw DDL in `sabi/schema.py`,
    including one *partial* index per live retrieval scope whose predicate has
    to be a literal. Alembic reflects them but cannot reproduce them, so left
    alone it proposes dropping them on every autogenerate -- and dropping a
    partial scope index silently returns fewer rows than `LIMIT` asks for,
    which is the single worst failure this codebase knows about.
    """
    if type_ == "index" and name and (
        "hnsw" in name or "trgm" in name or name.startswith("ix_chunks_tsv")
    ):
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_item=render_item,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_item=render_item,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
