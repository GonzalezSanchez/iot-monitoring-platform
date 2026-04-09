"""
Integration tests for lambdas/analyze/handler.py

Tests _load_rows, _insert_patterns, _insert_anomalies against a real DB.
"""

import json

import psycopg2.extensions
from analyze.handler import _insert_anomalies, _insert_patterns, _load_rows


def _insert_raw(
    conn: psycopg2.extensions.connection,
    event_id: str,
    ts: str = "2026-01-05T10:00:00+00:00",
    temperature: float = 21.5,
    room_id: str = "room-a",
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_sensor_data
                (event_id, device_id, room_id, ts, temperature, humidity,
                 motion, occupancy, raw_payload)
            VALUES (%s, 'dev-1', %s, %s, %s, 55.0, true, true, %s)
            """,
            (event_id, room_id, ts, temperature, json.dumps({})),
        )


class TestLoadRowsIntegration:
    def test_returns_rows_in_window(self, conn: psycopg2.extensions.connection) -> None:
        _insert_raw(conn, "an-evt-1", ts="2026-01-05T10:00:00+00:00")
        rows = _load_rows(conn, "2026-01-05", "2026-01-05")
        assert len(rows) >= 1
        assert any(r["room_id"] == "room-a" for r in rows)

    def test_returns_empty_outside_window(self, conn: psycopg2.extensions.connection) -> None:
        rows = _load_rows(conn, "2020-01-01", "2020-01-01")
        assert rows == []

    def test_row_has_expected_keys(self, conn: psycopg2.extensions.connection) -> None:
        _insert_raw(conn, "an-evt-keys")
        rows = _load_rows(conn, "2026-01-05", "2026-01-05")
        assert rows, "Expected at least one row"
        for key in ("room_id", "device_id", "ts", "temperature", "humidity", "motion", "occupancy"):
            assert key in rows[0]


class TestInsertPatternsIntegration:
    def test_inserts_patterns(self, conn: psycopg2.extensions.connection) -> None:
        patterns = [
            {
                "entity_type": "room",
                "entity_id": "room-a",
                "pattern_type": "occupancy_schedule",
                "data": json.dumps({"schedule": {"0": [9, 10]}}),
            }
        ]
        count = _insert_patterns(conn, "job-int-1", "2026-01-01", "2026-01-07", patterns)
        assert count == 1

        with conn.cursor() as cur:
            cur.execute("SELECT job_id, entity_id FROM patterns WHERE job_id = 'job-int-1'")
            row = cur.fetchone()
        assert row == ("job-int-1", "room-a")

    def test_empty_list_returns_zero(self, conn: psycopg2.extensions.connection) -> None:
        assert _insert_patterns(conn, "job-int-empty", "2026-01-01", "2026-01-07", []) == 0


class TestInsertAnomaliesIntegration:
    def test_inserts_anomalies(self, conn: psycopg2.extensions.connection) -> None:
        anomalies = [
            {
                "entity_type": "room",
                "entity_id": "room-b",
                "anomaly_type": "temperature_spike",
                "detected_at": "2026-01-05T09:00:00+00:00",
                "severity": "high",
                "data": json.dumps({"z_score": 3.5}),
            }
        ]
        count = _insert_anomalies(conn, "job-int-2", anomalies)
        assert count == 1

        with conn.cursor() as cur:
            cur.execute("SELECT severity FROM anomalies WHERE job_id = 'job-int-2'")
            row = cur.fetchone()
        assert row == ("high",)

    def test_empty_list_returns_zero(self, conn: psycopg2.extensions.connection) -> None:
        assert _insert_anomalies(conn, "job-int-empty2", []) == 0
