"""
Unit tests for scripts/migrate.py

Tests credential resolution and migration logic using mocked psycopg2.
No real database connection required.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# migrate.py lives in scripts/ — add to path so it can be imported
sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
import migrate  # noqa: E402  (import after sys.path manipulation)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_conn(execute_raises: Exception | None = None) -> MagicMock:
    """Return a mock psycopg2 connection with a cursor context manager."""
    cur = MagicMock()
    if execute_raises:
        cur.execute.side_effect = execute_raises
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cur
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    conn._cur = cur  # expose for assertions
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# get_connection_params — local path
# ──────────────────────────────────────────────────────────────────────────────


class TestGetConnectionParamsLocal:
    def test_returns_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SECRETS_MANAGER_SECRET_NAME", raising=False)
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "testdb")
        monkeypatch.setenv("DB_USER", "testuser")
        monkeypatch.setenv("DB_PASSWORD", "testpass")

        params = migrate.get_connection_params()

        assert params["host"] == "localhost"
        assert params["port"] == 5432
        assert params["dbname"] == "testdb"
        assert params["user"] == "testuser"
        assert params["password"] == "testpass"

    def test_default_port_is_5432(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SECRETS_MANAGER_SECRET_NAME", raising=False)
        monkeypatch.delenv("DB_PORT", raising=False)
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_NAME", "db")
        monkeypatch.setenv("DB_USER", "u")
        monkeypatch.setenv("DB_PASSWORD", "p")

        assert migrate.get_connection_params()["port"] == 5432

    def test_exits_when_required_vars_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SECRETS_MANAGER_SECRET_NAME", raising=False)
        monkeypatch.delenv("DB_HOST", raising=False)
        monkeypatch.delenv("DB_NAME", raising=False)
        monkeypatch.delenv("DB_USER", raising=False)
        monkeypatch.delenv("DB_PASSWORD", raising=False)

        with pytest.raises(SystemExit):
            migrate.get_connection_params()


# ──────────────────────────────────────────────────────────────────────────────
# get_connection_params — AWS path
# ──────────────────────────────────────────────────────────────────────────────


class TestGetConnectionParamsAWS:
    def _main_secret(self) -> dict:
        return {
            "host": "aurora.example.com",
            "port": 5432,
            "dbname": "p2a_prod",
            "username": "p2admin",
            "master_secret_arn": "arn:aws:secretsmanager:eu-central-1:123:secret:master",
        }

    def _master_secret(self) -> dict:
        return {"password": "supersecret"}

    def test_fetches_from_secrets_manager(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SECRETS_MANAGER_SECRET_NAME", "p2a-prod-db-credentials")
        monkeypatch.setenv("AWS_REGION", "eu-central-1")

        secrets = {
            "p2a-prod-db-credentials": self._main_secret(),
            "arn:aws:secretsmanager:eu-central-1:123:secret:master": self._master_secret(),
        }

        def fake_get_secret(secret_id: str, region: str) -> dict:
            return secrets[secret_id]

        with patch.object(migrate, "_get_secret", side_effect=fake_get_secret):
            params = migrate.get_connection_params()

        assert params["host"] == "aurora.example.com"
        assert params["password"] == "supersecret"
        assert params["user"] == "p2admin"


# ──────────────────────────────────────────────────────────────────────────────
# run_migrations
# ──────────────────────────────────────────────────────────────────────────────


class TestRunMigrations:
    _params = {
        "host": "localhost",
        "port": 5432,
        "dbname": "testdb",
        "user": "u",
        "password": "p",
    }

    def test_executes_all_ddl_statements(self) -> None:
        conn = _make_conn()
        with patch("psycopg2.connect", return_value=conn):
            migrate.run_migrations(self._params)

        assert conn._cur.execute.call_count == len(migrate.DDL_STATEMENTS)

    def test_commits_on_success(self) -> None:
        conn = _make_conn()
        with patch("psycopg2.connect", return_value=conn):
            migrate.run_migrations(self._params)

        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()

    def test_rollback_on_failure(self) -> None:
        conn = _make_conn(execute_raises=Exception("syntax error"))
        with patch("psycopg2.connect", return_value=conn):
            with pytest.raises(SystemExit):
                migrate.run_migrations(self._params)

        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()

    def test_connection_closed_after_success(self) -> None:
        conn = _make_conn()
        with patch("psycopg2.connect", return_value=conn):
            migrate.run_migrations(self._params)

        conn.close.assert_called_once()

    def test_connection_closed_after_failure(self) -> None:
        conn = _make_conn(execute_raises=Exception("boom"))
        with patch("psycopg2.connect", return_value=conn):
            with pytest.raises(SystemExit):
                migrate.run_migrations(self._params)

        conn.close.assert_called_once()

    def test_exits_when_connection_fails(self) -> None:
        import psycopg2 as pg2

        with patch("psycopg2.connect", side_effect=pg2.OperationalError("connection refused")):
            with pytest.raises(SystemExit):
                migrate.run_migrations(self._params)


# ──────────────────────────────────────────────────────────────────────────────
# Idempotency — DDL uses IF NOT EXISTS
# ──────────────────────────────────────────────────────────────────────────────


class TestDDLIdempotency:
    def test_create_table_statements_use_if_not_exists(self) -> None:
        create_statements = [s for s in migrate.DDL_STATEMENTS if "CREATE TABLE" in s.upper()]
        assert len(create_statements) == 3, "Expected 3 CREATE TABLE statements"
        for stmt in create_statements:
            assert "IF NOT EXISTS" in stmt.upper(), f"Missing IF NOT EXISTS in: {stmt[:60]}..."

    def test_create_index_statements_use_if_not_exists(self) -> None:
        index_statements = [s for s in migrate.DDL_STATEMENTS if "CREATE INDEX" in s.upper()]
        assert len(index_statements) > 0
        for stmt in index_statements:
            assert "IF NOT EXISTS" in stmt.upper(), f"Missing IF NOT EXISTS in: {stmt[:60]}..."

    def test_all_three_tables_defined(self) -> None:
        ddl_text = " ".join(migrate.DDL_STATEMENTS)
        for table in ("raw_sensor_data", "patterns", "anomalies"):
            assert table in ddl_text, f"Table '{table}' not found in DDL"
