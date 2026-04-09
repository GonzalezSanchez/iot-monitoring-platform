"""
Integration tests for lambdas/transform/handler.py

Tests _fetch_unprocessed and _delete_invalid against a real PostgreSQL instance.
"""

import json

import psycopg2.extensions
from transform.handler import _delete_invalid, _fetch_unprocessed


def _insert_raw(
    conn: psycopg2.extensions.connection,
    event_id: str,
    ts: str = "2026-01-05T10:00:00+00:00",
    temperature: float | None = 21.5,
    device_id: str = "dev-1",
    room_id: str = "room-a",
) -> int:
    """Insert a raw_sensor_data row and return its id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_sensor_data
                (event_id, device_id, room_id, ts, temperature, humidity,
                 motion, occupancy, raw_payload)
            VALUES (%s, %s, %s, %s, %s, 55.0, true, true, %s)
            RETURNING id
            """,
            (event_id, device_id, room_id, ts, temperature, json.dumps({})),
        )
        return cur.fetchone()[0]


class TestFetchUnprocessedIntegration:
    def test_returns_rows_in_window(self, conn: psycopg2.extensions.connection) -> None:
        _insert_raw(conn, "tf-evt-1", ts="2026-01-05T10:00:00+00:00")
        rows = _fetch_unprocessed(conn, "2026-01-05", "2026-01-05")
        assert len(rows) == 1
        assert rows[0].event_id == "tf-evt-1"

    def test_excludes_rows_outside_window(self, conn: psycopg2.extensions.connection) -> None:
        _insert_raw(conn, "tf-evt-out", ts="2026-01-10T10:00:00+00:00")
        rows = _fetch_unprocessed(conn, "2026-01-05", "2026-01-05")
        ids = [r.event_id for r in rows]
        assert "tf-evt-out" not in ids

    def test_returns_empty_for_empty_table(self, conn: psycopg2.extensions.connection) -> None:
        rows = _fetch_unprocessed(conn, "2020-01-01", "2020-01-01")
        assert rows == []


class TestDeleteInvalidIntegration:
    def test_deletes_rows_by_id(self, conn: psycopg2.extensions.connection) -> None:
        row_id = _insert_raw(conn, "tf-del-1")
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM raw_sensor_data WHERE id = %s", (row_id,))
            assert cur.fetchone()[0] == 1

        _delete_invalid(conn, [row_id])

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM raw_sensor_data WHERE id = %s", (row_id,))
            assert cur.fetchone()[0] == 0

    def test_empty_list_is_noop(self, conn: psycopg2.extensions.connection) -> None:
        """_delete_invalid([]) must not raise."""
        _delete_invalid(conn, [])
