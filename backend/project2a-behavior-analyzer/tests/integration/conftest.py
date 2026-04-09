"""
Shared fixtures for integration tests.

Requires a running PostgreSQL instance (docker/docker-compose.yml).
Start with:  docker compose -f docker/docker-compose.yml up -d

Connection details match docker-compose.yml defaults:
  host=localhost  port=5432  dbname=p2_dev  user=dev  password=dev

Isolation strategy:
  - Schema is created once per session via migrate().
  - After every test the _clean fixture TRUNCATEs all tables so that
    production code that calls conn.commit() internally does not bleed
    data into subsequent tests.
  - The conn fixture rolls back any uncommitted writes added by the test
    itself before _clean runs.
"""

import os
import sys
from collections.abc import Generator
from pathlib import Path

import psycopg2
import psycopg2.extensions
import pytest

# ── Env vars so Lambda handlers can call get_connection() without AWS ─────────
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "p2_dev")
os.environ.setdefault("DB_USER", "dev")
os.environ.setdefault("DB_PASSWORD", "dev")
os.environ.pop("SECRETS_MANAGER_SECRET_NAME", None)

# make scripts/ and lambdas/ importable
_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT / "lambdas"))

import migrate  # noqa: E402

# ──────────────────────────────────────────────────────────────────────────────
# Connection constants — match docker-compose.yml
# ──────────────────────────────────────────────────────────────────────────────

_DSN = {
    "host": "localhost",
    "port": 5432,
    "dbname": "p2_dev",
    "user": "dev",
    "password": "dev",
}


# ──────────────────────────────────────────────────────────────────────────────
# Session-scoped: create schema once
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Run migrate.py once for the whole test session."""
    migrate.run_migrations(dict(_DSN))


# ──────────────────────────────────────────────────────────────────────────────
# Function-scoped autouse: truncate all tables after every test.
# Production Lambda functions commit internally, so transaction rollback alone
# is insufficient — a full TRUNCATE is required for isolation.
# Being autouse means it sets up first and tears down last (after conn).
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean() -> Generator[None, None, None]:
    """Truncate all data tables after each test."""
    yield
    _c = psycopg2.connect(**_DSN)
    try:
        with _c.cursor() as cur:
            cur.execute("TRUNCATE raw_sensor_data, patterns, anomalies RESTART IDENTITY CASCADE")
        _c.commit()
    finally:
        _c.close()


# ──────────────────────────────────────────────────────────────────────────────
# Function-scoped: connection for tests that call internal helpers directly
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def conn() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Yields a psycopg2 connection for the test.
    Rolls back any uncommitted changes after the test.
    Handles the case where production code already closed the connection.
    """
    connection = psycopg2.connect(**_DSN)
    connection.autocommit = False
    try:
        yield connection
    finally:
        if not connection.closed:
            connection.rollback()
        if not connection.closed:
            connection.close()


@pytest.fixture()
def dsn() -> dict:
    """Raw DSN dict for tests that need to open their own connection."""
    return dict(_DSN)
