"""Test fixtures.

The tests run against a real Postgres with pgvector, not a mock. The retrieval
layer is half SQL -- tsvector ranking, cosine distance, the lateral join in the
exclusion query -- and a mocked database would test none of it.

Environment is set before any `sabi` import, because settings are cached on
first use by design.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import psycopg
import pytest

TEST_DB = "sabi_test"
ADMIN_URL = os.environ.get(
    "SABI_TEST_ADMIN_URL", "postgresql://sabi:sabi@localhost:5433/postgres"
)
TEST_URL = os.environ.get(
    "SABI_TEST_DATABASE_URL",
    f"postgresql+psycopg://sabi:sabi@localhost:5433/{TEST_DB}",
)


def _ensure_database() -> None:
    with psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=15) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{TEST_DB}"')


_ensure_database()

_ARTIFACTS = Path(tempfile.mkdtemp(prefix="sabi-test-artifacts-"))
os.environ["SABI_DATABASE_URL"] = TEST_URL
os.environ["SABI_ARTIFACT_DIR"] = str(_ARTIFACTS)
os.environ["SABI_LLM_PROVIDER"] = "offline"
os.environ["SABI_EMBEDDING_PROVIDER"] = "local_lsa"
os.environ["SABI_ADMIN_TOKEN"] = "test-admin-token"
os.environ["SABI_IP_HASH_SALT"] = "test-salt"


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    from sabi.corpus.ingest import apply_ingest
    from sabi.schema import bootstrap

    bootstrap()
    apply_ingest(None, prune=True, refit=True)


# Everything except these is traffic, and traffic is wiped between tests. Naming
# what to *keep* rather than what to clear means a new table is cleaned the day
# it is added -- the previous hardcoded TRUNCATE list silently leaked state from
# any table nobody remembered to add to it, and the bare `DELETE FROM users` that
# followed it would fail outright on the first table to reference users.
KEEP_BETWEEN_TESTS = frozenset({"documents", "chunks", "plans", "system_state"})


@pytest.fixture(autouse=True)
def clean_traffic():
    """Each test starts with no requests, users or feedback.

    The corpus is left in place: re-ingesting per test would dominate the run
    time and the corpus is read-only as far as these tests are concerned.
    """
    yield
    from sqlalchemy import text

    from sabi.db import session_scope
    from sabi.models import Base

    tables = [
        t.name for t in Base.metadata.sorted_tables
        if t.name not in KEEP_BETWEEN_TESTS
    ]
    # CASCADE covers dependents; users is truncated with the rest rather than
    # deleted after, so order does not matter and foreign keys cannot block it.
    with session_scope() as s:
        s.execute(
            text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
        )


@pytest.fixture
def session():
    from sabi.db import session_scope

    with session_scope() as s:
        yield s


# Every state-changing POST carries a CSRF token, which is bound to the
# caller's session or, for an anonymous visitor, to their signed id cookie.
# Rather than thread that through sixty call sites, the test client fetches a
# token the same way a browser would -- by loading a page that has a form on
# it -- and fills the field in when the test did not.
#
# Tests that want to check the protection itself pass `csrf_token=""`
# explicitly, which is honoured and not overwritten.
CSRF_FIELD = re.compile(r'name="csrf_token" value="([^"]+)"')


class FormClient:
    """A TestClient that fills in the CSRF field, as a browser would."""

    def __init__(self, app) -> None:
        from fastapi.testclient import TestClient

        self._client = TestClient(app)

    def __getattr__(self, name):
        return getattr(self._client, name)

    def csrf(self) -> str:
        # /app carries the composer, and the GET also establishes the signed
        # anonymous cookie that the token is derived from.
        page = self._client.get("/app")
        found = CSRF_FIELD.search(page.text)
        assert found, "no CSRF field on /app -- has the composer changed?"
        return found.group(1)

    def post(self, url, **kwargs):
        data = kwargs.get("data")
        if isinstance(data, dict) and "csrf_token" not in data:
            data = dict(data)
            data["csrf_token"] = self.csrf()
            kwargs["data"] = data
        return self._client.post(url, **kwargs)


@pytest.fixture
def client():
    from sabi.api.app import app

    return FormClient(app)
