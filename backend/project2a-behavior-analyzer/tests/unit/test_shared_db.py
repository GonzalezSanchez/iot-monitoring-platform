"""
Unit tests for lambdas/shared/db.py
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from shared.db import _connection_params, _get_secret, get_connection

# ──────────────────────────────────────────────────────────────────────────────
# _get_secret
# ──────────────────────────────────────────────────────────────────────────────


class TestGetSecret:
    def test_parses_secret_string(self) -> None:
        payload = {"username": "admin", "password": "s3cr3t"}
        client = MagicMock()
        client.get_secret_value.return_value = {"SecretString": json.dumps(payload)}

        with patch("shared.db.boto3.client", return_value=client):
            result = _get_secret("my-secret", "eu-central-1")

        assert result == payload


# ──────────────────────────────────────────────────────────────────────────────
# _connection_params — local path (no SECRETS_MANAGER_SECRET_NAME)
# ──────────────────────────────────────────────────────────────────────────────


class TestConnectionParamsLocal:
    def test_reads_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SECRETS_MANAGER_SECRET_NAME", raising=False)
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_NAME", "testdb")
        monkeypatch.setenv("DB_USER", "testuser")
        monkeypatch.setenv("DB_PASSWORD", "testpass")
        monkeypatch.setenv("DB_PORT", "5433")

        params = _connection_params()

        assert params["host"] == "localhost"
        assert params["dbname"] == "testdb"
        assert params["user"] == "testuser"
        assert params["password"] == "testpass"
        assert params["port"] == 5433

    def test_default_port_is_5432(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SECRETS_MANAGER_SECRET_NAME", raising=False)
        monkeypatch.delenv("DB_PORT", raising=False)
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_NAME", "testdb")
        monkeypatch.setenv("DB_USER", "testuser")
        monkeypatch.setenv("DB_PASSWORD", "testpass")

        assert _connection_params()["port"] == 5432


# ──────────────────────────────────────────────────────────────────────────────
# _connection_params — AWS path (SECRETS_MANAGER_SECRET_NAME is set)
# ──────────────────────────────────────────────────────────────────────────────


class TestConnectionParamsAWS:
    def _main_secret(self) -> dict:
        return {
            "host": "aurora.example.com",
            "port": "5432",
            "dbname": "prod",
            "username": "lambda_user",
            "master_secret_arn": "arn:aws:secretsmanager:eu-central-1:123:secret:master",
        }

    def _master_secret(self) -> dict:
        return {"password": "super-secret"}

    def test_fetches_host_and_credentials_from_secrets_manager(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SECRETS_MANAGER_SECRET_NAME", "prod/db")
        monkeypatch.setenv("AWS_REGION", "eu-central-1")

        main = self._main_secret()
        master = self._master_secret()

        with patch("shared.db._get_secret", side_effect=[main, master]):
            params = _connection_params()

        assert params["host"] == "aurora.example.com"
        assert params["dbname"] == "prod"
        assert params["user"] == "lambda_user"
        assert params["password"] == "super-secret"
        assert params["port"] == 5432

    def test_reraises_secrets_manager_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from botocore.exceptions import ClientError

        monkeypatch.setenv("SECRETS_MANAGER_SECRET_NAME", "prod/db")
        err = ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": ""}}, "op")

        with patch("shared.db._get_secret", side_effect=err):
            with pytest.raises(ClientError):
                _connection_params()


# ──────────────────────────────────────────────────────────────────────────────
# get_connection
# ──────────────────────────────────────────────────────────────────────────────


class TestGetConnection:
    def test_calls_psycopg2_connect_with_params(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SECRETS_MANAGER_SECRET_NAME", raising=False)
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_NAME", "testdb")
        monkeypatch.setenv("DB_USER", "testuser")
        monkeypatch.setenv("DB_PASSWORD", "testpass")

        mock_conn = MagicMock()
        with patch("shared.db.psycopg2.connect", return_value=mock_conn) as mock_connect:
            conn = get_connection()

        assert conn is mock_conn
        mock_connect.assert_called_once_with(
            host="localhost", port=5432, dbname="testdb", user="testuser", password="testpass"
        )
