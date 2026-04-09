"""
Integration tests for lambdas/api/ handlers.

Tests get_patterns and get_insights against a real PostgreSQL instance.
post_analyze is excluded — it calls Step Functions (AWS), covered by unit tests.

The handlers open their own connections via get_connection(), which reads the
DB_* env vars set in conftest.py.  No connection patching is needed.
"""

import json

import psycopg2
from api.get_insights import handler as get_insights
from api.get_patterns import handler as get_patterns

_DSN = {
    "host": "localhost",
    "port": 5432,
    "dbname": "p2_dev",
    "user": "dev",
    "password": "dev",
}


def _insert_pattern(job_id: str, entity_id: str) -> None:
    c = psycopg2.connect(**_DSN)
    try:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO patterns
                    (job_id, entity_type, entity_id, pattern_type, period_start, period_end, data)
                VALUES (%s, 'room', %s, 'occupancy_schedule', '2026-01-01', '2026-01-07', %s)
                """,
                (job_id, entity_id, json.dumps({"schedule": {"0": [9]}})),
            )
        c.commit()
    finally:
        c.close()


def _insert_anomaly(job_id: str, entity_id: str) -> None:
    c = psycopg2.connect(**_DSN)
    try:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO anomalies
                    (job_id, entity_type, entity_id, anomaly_type,
                     detected_at, severity, data)
                VALUES (%s, 'room', %s, 'temperature_spike',
                        '2026-01-05T09:00:00+00:00', 'medium', %s)
                """,
                (job_id, entity_id, json.dumps({})),
            )
        c.commit()
    finally:
        c.close()


def _event(path_params: dict) -> dict:
    return {"httpMethod": "GET", "pathParameters": path_params, "body": None}


class TestGetPatternsIntegration:
    def test_returns_patterns_for_job(self) -> None:
        _insert_pattern("api-job-1", "room-a")
        result = get_patterns(_event({"job_id": "api-job-1"}), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["patterns"]) == 1
        assert body["patterns"][0]["entity_id"] == "room-a"

    def test_returns_empty_for_unknown_job(self) -> None:
        result = get_patterns(_event({"job_id": "no-such-job"}), None)
        assert result["statusCode"] == 200
        assert json.loads(result["body"])["patterns"] == []


class TestGetInsightsIntegration:
    def test_returns_patterns_and_anomalies(self) -> None:
        _insert_pattern("api-job-2", "room-b")
        _insert_anomaly("api-job-2", "room-b")
        result = get_insights(_event({"entity_type": "room", "entity_id": "room-b"}), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["patterns"]) == 1
        assert len(body["anomalies"]) == 1
        assert body["anomalies"][0]["severity"] == "medium"

    def test_returns_empty_for_unknown_entity(self) -> None:
        result = get_insights(_event({"entity_type": "room", "entity_id": "no-such-room"}), None)
        body = json.loads(result["body"])
        assert body["patterns"] == []
        assert body["anomalies"] == []
