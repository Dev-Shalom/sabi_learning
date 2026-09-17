"""Test fixtures.

The tests run against a real Postgres with pgvector, not a mock. The retrieval
layer is half SQL -- tsvector ranking, cosine distance, the lateral join in the
exclusion query -- and a mocked database would test none of it.

Environment is set before any `sabi` import, because settings are cached on
first use by design.
"""

from __future__ import annotations

import os
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


@pytest.fixture(autouse=True)
def clean_traffic():
    """Each test starts with no requests, users or feedback.

    The corpus is left in place: re-ingesting per test would dominate the run
    time and the corpus is read-only as far as these tests are concerned.
    """
    yield
    from sqlalchemy import text

    from sabi.db import session_scope

    with session_scope() as s:
        s.execute(text("TRUNCATE feedback, usage_events, requests, waitlist, "
                       "golden_items, answer_cache RESTART IDENTITY CASCADE"))
        s.execute(text("DELETE FROM users"))


@pytest.fixture
def session():
    from sabi.db import session_scope

    with session_scope() as s:
        yield s


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from sabi.api.app import app

    return TestClient(app)
