"""
Unit tests for lambdas/api/ handlers — written BEFORE implementation ([9t] before [9]).

Three handlers under test:
  - post_analyze   : POST /analyze/patterns  → starts Step Functions execution
  - get_patterns   : GET  /analyze/patterns/{job_id} → query patterns table
  - get_insights   : GET  /insights/{entity_type}/{entity_id} → patterns + anomalies
"""

import json
from collections.abc import Sequence
from unittest.mock import MagicMock, patch

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _api_event(method: str, path_params: dict | None = None, body: dict | None = None) -> dict:
    """Minimal API Gateway v1 proxy event."""
    return {
        "httpMethod": method,
        "pathParameters": path_params or {},
        "body": json.dumps(body) if body is not None else None,
    }


def _conn(rows: Sequence[Sequence]) -> MagicMock:
    """Mock psycopg2 connection where cursor.fetchall() returns rows."""
    cur = MagicMock()
    cur.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cur
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# POST /analyze/patterns  (post_analyze handler)
# ──────────────────────────────────────────────────────────────────────────────


class TestPostAnalyze:
    def _event(self, body: dict | None = None) -> dict:
        return _api_event("POST", body=body or {"days_back": 7})

    def test_returns_200_with_execution_arn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("STATE_MACHINE_ARN", "arn:aws:states:eu-central-1:123:stateMachine:etl")

        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:eu-central-1:123:execution:etl:abc"
        }

        with patch("api.post_analyze.boto3.client", return_value=mock_sfn):
            from api.post_analyze import handler

            result = handler(self._event(), None)

        assert result["statusCode"] == 202
        body = json.loads(result["body"])
        assert "execution_arn" in body

    def test_passes_days_back_to_step_functions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("STATE_MACHINE_ARN", "arn:aws:states:eu-central-1:123:stateMachine:etl")

        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {"executionArn": "arn:..."}

        with patch("api.post_analyze.boto3.client", return_value=mock_sfn):
            from api.post_analyze import handler

            handler(_api_event("POST", body={"days_back": 14}), None)

        call_input = json.loads(mock_sfn.start_execution.call_args.kwargs["input"])
        assert call_input["days_back"] == 14

    def test_returns_400_when_body_is_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("STATE_MACHINE_ARN", "arn:aws:states:eu-central-1:123:stateMachine:etl")

        from api.post_analyze import handler

        event = _api_event("POST", body=None)
        result = handler(event, None)

        assert result["statusCode"] == 400

    def test_uses_default_days_back_when_not_provided(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("STATE_MACHINE_ARN", "arn:aws:states:eu-central-1:123:stateMachine:etl")

        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {"executionArn": "arn:..."}

        with patch("api.post_analyze.boto3.client", return_value=mock_sfn):
            from api import post_analyze

            result = post_analyze.handler(_api_event("POST", body={}), None)

        assert result["statusCode"] == 202
        call_input = json.loads(mock_sfn.start_execution.call_args.kwargs["input"])
        assert call_input["days_back"] == 7  # default


# ──────────────────────────────────────────────────────────────────────────────
# GET /analyze/patterns/{job_id}  (get_patterns handler)
# ──────────────────────────────────────────────────────────────────────────────


class TestGetPatterns:
    def _event(self, job_id: str = "job-1") -> dict:
        return _api_event("GET", path_params={"job_id": job_id})

    def test_returns_200_with_patterns_list(self) -> None:
        db_rows = [
            ("job-1", "room", "room-a", "occupancy_schedule", "{}", "2026-01-01", "2026-01-07")
        ]
        conn = _conn(db_rows)

        with (
            patch("api.get_patterns.get_connection", return_value=conn),
        ):
            from api.get_patterns import handler

            result = handler(self._event(), None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert isinstance(body["patterns"], list)
        assert len(body["patterns"]) == 1

    def test_returns_empty_list_when_no_patterns(self) -> None:
        with patch("api.get_patterns.get_connection", return_value=_conn([])):
            from api.get_patterns import handler

            result = handler(self._event("job-999"), None)

        assert result["statusCode"] == 200
        assert json.loads(result["body"])["patterns"] == []

    def test_pattern_contains_expected_fields(self) -> None:
        db_rows = [
            ("job-1", "room", "room-a", "occupancy_schedule", "{}", "2026-01-01", "2026-01-07")
        ]
        with patch("api.get_patterns.get_connection", return_value=_conn(db_rows)):
            from api.get_patterns import handler

            result = handler(self._event(), None)

        pattern = json.loads(result["body"])["patterns"][0]
        for field in ("job_id", "entity_type", "entity_id", "pattern_type", "data"):
            assert field in pattern

    def test_closes_db_connection(self) -> None:
        conn = _conn([])
        with patch("api.get_patterns.get_connection", return_value=conn):
            from api.get_patterns import handler

            handler(self._event(), None)

        conn.close.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# GET /insights/{entity_type}/{entity_id}  (get_insights handler)
# ──────────────────────────────────────────────────────────────────────────────


class TestGetInsights:
    def _event(self, entity_type: str = "room", entity_id: str = "room-a") -> dict:
        return _api_event("GET", path_params={"entity_type": entity_type, "entity_id": entity_id})

    def _pattern_row(self) -> tuple:
        return ("job-1", "room", "room-a", "occupancy_schedule", "{}", "2026-01-01", "2026-01-07")

    def _anomaly_row(self) -> tuple:
        return (
            "job-1",
            "room",
            "room-a",
            "temperature",
            "2026-01-05T09:00:00+00:00",
            "medium",
            "{}",
        )

    def test_returns_200_with_patterns_and_anomalies(self) -> None:
        cur = MagicMock()
        cur.fetchall.side_effect = [[self._pattern_row()], [self._anomaly_row()]]
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("api.get_insights.get_connection", return_value=conn):
            from api.get_insights import handler

            result = handler(self._event(), None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["patterns"]) == 1
        assert len(body["anomalies"]) == 1

    def test_returns_empty_lists_when_no_data(self) -> None:
        cur = MagicMock()
        cur.fetchall.side_effect = [[], []]
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("api.get_insights.get_connection", return_value=conn):
            from api.get_insights import handler

            result = handler(self._event("room", "room-unknown"), None)

        body = json.loads(result["body"])
        assert body["patterns"] == []
        assert body["anomalies"] == []

    def test_anomaly_contains_severity_field(self) -> None:
        cur = MagicMock()
        cur.fetchall.side_effect = [[], [self._anomaly_row()]]
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("api.get_insights.get_connection", return_value=conn):
            from api.get_insights import handler

            result = handler(self._event(), None)

        anomaly = json.loads(result["body"])["anomalies"][0]
        assert anomaly["severity"] == "medium"

    def test_closes_db_connection(self) -> None:
        cur = MagicMock()
        cur.fetchall.side_effect = [[], []]
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("api.get_insights.get_connection", return_value=conn):
            from api.get_insights import handler

            handler(self._event(), None)

        conn.close.assert_called_once()
