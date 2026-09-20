#!/usr/bin/env python
"""Does an *existing* database, brought forward by `bootstrap()`, match the ORM?

`sabi/schema.py` creates the schema with `Base.metadata.create_all` plus a
forward-only list of idempotent `ALTER`s. The trap that list exists for is that
`create_all` silently ignores columns added to a table that already exists: it
creates missing *tables* and nothing else. So a new `mapped_column` with no
matching `MIGRATIONS` entry works perfectly on every fresh database -- including
every database CI has ever built -- and is missing only where it matters, on the
one database that already had rows in it.

That asymmetry means the bug is structurally invisible to the normal test suite.
This script closes it by inspecting a live database and diffing it against the
ORM metadata. Run against a database created by an older revision and then
brought forward, a missing `MIGRATIONS` entry shows up as a missing column.

    python tools/schema_drift.py

Exits 0 when the database carries everything the ORM declares, 1 otherwise,
naming each gap and the `MIGRATIONS` line that would close it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect  # noqa: E402

from sabi.db import engine  # noqa: E402
from sabi.models import Base  # noqa: E402


def sql_type(column) -> str:
    """The column type as DDL would spell it, for a copy-pasteable suggestion."""
    try:
        return column.type.compile(dialect=engine().dialect)
    except Exception:  # pragma: no cover - exotic types only
        return str(column.type)


def main() -> int:
    inspector = inspect(engine())
    live_tables = set(inspector.get_table_names())

    missing_tables: list[str] = []
    missing_columns: list[tuple[str, str, str, bool]] = []
    missing_indexes: list[tuple[str, str]] = []

    for table in Base.metadata.sorted_tables:
        if table.name not in live_tables:
            # create_all handles this case, so it is only reachable if bootstrap
            # was never run -- still worth reporting rather than crashing below.
            missing_tables.append(table.name)
            continue

        live_columns = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in live_columns:
                missing_columns.append(
                    (table.name, column.name, sql_type(column), column.nullable)
                )

        live_indexes = {i["name"] for i in inspector.get_indexes(table.name)}
        live_indexes |= {
            c["name"] for c in inspector.get_unique_constraints(table.name)
        }
        for index in table.indexes:
            if index.name not in live_indexes:
                missing_indexes.append((table.name, index.name))

    if not (missing_tables or missing_columns or missing_indexes):
        counts = f"{len(Base.metadata.sorted_tables)} tables"
        print(f"schema matches the ORM ({counts})")
        return 0

    print("SCHEMA DRIFT -- this database is behind the ORM\n")

    if missing_tables:
        print("  tables absent (has bootstrap() run?):")
        for name in missing_tables:
            print(f"    {name}")
        print()

    if missing_columns:
        print("  columns absent -- each needs a MIGRATIONS entry in sabi/schema.py:")
        for table, column, type_, nullable in missing_columns:
            null = "" if nullable else " NOT NULL DEFAULT <value>"
            print(
                f'    "ALTER TABLE {table} '
                f'ADD COLUMN IF NOT EXISTS {column} {type_}{null}",'
            )
        print()

    if missing_indexes:
        print("  indexes absent -- add to POST_DDL in sabi/schema.py:")
        for table, name in missing_indexes:
            print(f"    CREATE INDEX IF NOT EXISTS {name} ON {table} (...)")
        print()

    print(
        "A fresh database would pass: create_all builds missing tables but never\n"
        "alters an existing one. Only a database that predates the change shows this."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
