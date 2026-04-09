"""
Shared fixtures for regression tests.

Requires a running PostgreSQL instance (docker/docker-compose.yml).
Start with:  docker compose -f docker/docker-compose.yml up -d

Connection details match docker-compose.yml defaults:
  host=localhost  port=5432  dbname=p2_dev  user=dev  password=dev

Isolation strategy: TRUNCATE all tables after every test, mirroring
the integration-test approach (handlers commit internally, so rollback alone
is insufficient).
"""

import os
import sys
from collections.abc import Generator
from pathlib import Path

import psycopg2
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

_DSN = {
    "host": "localhost",
    "port": 5432,
    "dbname": "p2_dev",
    "user": "dev",
    "password": "dev",
}


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Run migrate.py once for the whole test session."""
    migrate.run_migrations(dict(_DSN))


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
