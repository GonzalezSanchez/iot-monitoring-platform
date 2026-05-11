import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.migrate import DDL_STATEMENTS, get_connection_params, run_migrations


class TestGetConnectionParams:
    def test_returns_params_when_all_env_vars_set(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "p2b_dev")
        monkeypatch.setenv("DB_USER", "p2b_admin")
        monkeypatch.setenv("DB_PASSWORD", "dev")

        params = get_connection_params()

        assert params["host"] == "localhost"
        assert params["port"] == 5432
        assert params["dbname"] == "p2b_dev"
        assert params["user"] == "p2b_admin"
        assert params["password"] == "dev"

    def test_exits_when_env_vars_missing(self, monkeypatch):
        for var in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
            monkeypatch.delenv(var, raising=False)

        with pytest.raises(SystemExit):
            get_connection_params()

    def test_default_port_is_5432(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_NAME", "p2b_dev")
        monkeypatch.setenv("DB_USER", "p2b_admin")
        monkeypatch.setenv("DB_PASSWORD", "dev")
        monkeypatch.delenv("DB_PORT", raising=False)

        params = get_connection_params()

        assert params["port"] == 5432


class TestRunMigrations:
    def _make_conn(self):
        cur = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn, cur

    def test_executes_all_ddl_statements(self):
        conn, cur = self._make_conn()
        params = {
            "host": "localhost",
            "port": 5432,
            "dbname": "p2b_dev",
            "user": "p2b_admin",
            "password": "dev",
        }

        with patch("scripts.migrate.psycopg2.connect", return_value=conn):
            run_migrations(params)

        assert cur.execute.call_count == len(DDL_STATEMENTS)

    def test_commits_on_success(self):
        conn, _ = self._make_conn()
        params = {
            "host": "localhost",
            "port": 5432,
            "dbname": "p2b_dev",
            "user": "p2b_admin",
            "password": "dev",
        }

        with patch("scripts.migrate.psycopg2.connect", return_value=conn):
            run_migrations(params)

        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()

    def test_rolls_back_on_error(self):
        conn, cur = self._make_conn()
        cur.execute.side_effect = Exception("syntax error")
        params = {
            "host": "localhost",
            "port": 5432,
            "dbname": "p2b_dev",
            "user": "p2b_admin",
            "password": "dev",
        }

        with patch("scripts.migrate.psycopg2.connect", return_value=conn):
            with pytest.raises(SystemExit):
                run_migrations(params)

        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()

    def test_closes_connection_on_success(self):
        conn, _ = self._make_conn()
        params = {
            "host": "localhost",
            "port": 5432,
            "dbname": "p2b_dev",
            "user": "p2b_admin",
            "password": "dev",
        }

        with patch("scripts.migrate.psycopg2.connect", return_value=conn):
            run_migrations(params)

        conn.close.assert_called_once()

    def test_closes_connection_on_error(self):
        conn, cur = self._make_conn()
        cur.execute.side_effect = Exception("syntax error")
        params = {
            "host": "localhost",
            "port": 5432,
            "dbname": "p2b_dev",
            "user": "p2b_admin",
            "password": "dev",
        }

        with patch("scripts.migrate.psycopg2.connect", return_value=conn):
            with pytest.raises(SystemExit):
                run_migrations(params)

        conn.close.assert_called_once()


class TestDdlStatements:
    def test_all_tables_present(self):
        combined = " ".join(DDL_STATEMENTS).lower()
        for table in ("raw_sensor_data", "processed_sensor_data", "patterns", "anomalies"):
            assert table in combined

    def test_pgvector_extension_present(self):
        assert any("vector" in s.lower() for s in DDL_STATEMENTS)

    def test_processed_column_in_raw_sensor_data(self):
        raw_ddl = next(s for s in DDL_STATEMENTS if "raw_sensor_data" in s and "CREATE TABLE" in s)
        assert "processed" in raw_ddl
