"""
Integration tests for lambdas/extract/handler.py

Tests _upsert_batch against a real PostgreSQL instance.
"""

import json

import psycopg2.extensions
from extract.handler import _upsert_batch


def _make_row(event_id: str = "evt-1") -> dict:
    return {
        "event_id": event_id,
        "device_id": "dev-1",
        "room_id": "room-a",
        "ts": "2026-01-05T10:00:00+00:00",
        "temperature": 21.5,
        "humidity": 55.0,
        "motion": True,
        "occupancy": True,
        "raw_payload": json.dumps({"temperature": 21.5, "humidity": 55.0}),
    }


def _count_rows(conn: psycopg2.extensions.connection) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM raw_sensor_data")
        return cur.fetchone()[0]


class TestUpsertBatchIntegration:
    def test_inserts_new_rows(self, conn: psycopg2.extensions.connection) -> None:
        rows = [_make_row("evt-int-1"), _make_row("evt-int-2")]
        inserted = _upsert_batch(conn, rows)
        assert inserted == 2
        assert _count_rows(conn) == 2

    def test_skips_duplicate_event_id(self, conn: psycopg2.extensions.connection) -> None:
        row = _make_row("evt-int-dup")
        _upsert_batch(conn, [row])
        inserted = _upsert_batch(conn, [row])  # same event_id
        assert inserted == 0

    def test_empty_list_returns_zero(self, conn: psycopg2.extensions.connection) -> None:
        assert _upsert_batch(conn, []) == 0

    def test_partial_duplicates(self, conn: psycopg2.extensions.connection) -> None:
        _upsert_batch(conn, [_make_row("evt-int-a")])
        inserted = _upsert_batch(conn, [_make_row("evt-int-a"), _make_row("evt-int-b")])
        assert inserted == 1  # only the new one
