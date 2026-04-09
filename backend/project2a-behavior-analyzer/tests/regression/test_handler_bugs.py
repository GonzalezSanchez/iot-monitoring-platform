"""
Regression tests — guard against bugs found during integration testing (2026-04).

REG-001  _upsert_batch calls conn.commit() internally.
         Bug: when the test passed its own conn to _upsert_batch, the internal
         commit flushed the test's entire pending transaction, making data
         visible across tests and breaking rollback-based isolation.
         Risk if commit is removed: Extract Lambda inserts disappear silently;
         Transform sees an empty table in every production run.

REG-002  _delete_invalid calls conn.commit() internally.
         Bug: same root cause as REG-001 — internal commit broke test isolation.
         Risk if commit is removed: rejected rows are never physically deleted
         and are re-fetched by every subsequent Transform + Analyze run.

REG-003  API handlers (get_patterns, get_insights) manage their own connection
         lifecycle — they open and close the connection internally.
         Bug: early test approach patched the shared test conn into the handler;
         the handler then called conn.close(), leaving fixture teardown with a
         closed connection and raising "connection already closed".
         Risk if close() is removed: connection leak on every Lambda invocation
         exhausts the PostgreSQL max_connections in the warm Lambda path.

All three tests require a running PostgreSQL instance:
  docker compose -f docker/docker-compose.yml up -d
"""

import json

import psycopg2
import pytest
from api.get_insights import handler as get_insights
from api.get_patterns import handler as get_patterns
from extract.handler import _upsert_batch
from transform.handler import _delete_invalid

_DSN = {
    "host": "localhost",
    "port": 5432,
    "dbname": "p2_dev",
    "user": "dev",
    "password": "dev",
}


def _fresh_conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(**_DSN)


def _count_raw(conn: psycopg2.extensions.connection) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM raw_sensor_data")
        return cur.fetchone()[0]


def _make_row(event_id: str) -> dict:
    return {
        "event_id": event_id,
        "device_id": "dev-reg",
        "room_id": "room-reg",
        "ts": "2026-01-05T10:00:00+00:00",
        "temperature": 21.5,
        "humidity": 55.0,
        "motion": True,
        "occupancy": True,
        "raw_payload": json.dumps({"temperature": 21.5}),
    }


def _http_event(path_params: dict) -> dict:
    return {"httpMethod": "GET", "pathParameters": path_params, "body": None}


# ──────────────────────────────────────────────────────────────────────────────
# REG-001: _upsert_batch must commit its writes durably
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.regression
class TestReg001UpsertCommitsInternally:
    def test_rows_visible_on_fresh_connection_after_write_conn_closed(self) -> None:
        """
        REG-001: _upsert_batch must call conn.commit() so that inserted rows
        survive after the writing connection is discarded.  A brand-new
        connection opened afterwards must see the rows.  If the internal commit
        is removed, this test fails and the Extract Lambda silently drops data.
        """
        conn_write = _fresh_conn()
        try:
            _upsert_batch(conn_write, [_make_row("reg-001-a")])
        finally:
            conn_write.close()

        conn_read = _fresh_conn()
        try:
            count = _count_raw(conn_read)
        finally:
            conn_read.close()

        assert count == 1, (
            "REG-001: row not visible after writing connection closed — "
            "_upsert_batch may not be committing"
        )

    def test_second_upsert_call_on_same_connection_does_not_raise(self) -> None:
        """
        REG-001b: after _upsert_batch commits internally, the connection must
        still be usable for a second call.  This guards against _upsert_batch
        accidentally closing or corrupting the connection after committing.
        """
        conn = _fresh_conn()
        try:
            _upsert_batch(conn, [_make_row("reg-001-b")])
            _upsert_batch(conn, [_make_row("reg-001-c")])  # same conn, second call
        finally:
            conn.close()

        conn_read = _fresh_conn()
        try:
            count = _count_raw(conn_read)
        finally:
            conn_read.close()

        assert count == 2, "REG-001b: expected 2 rows after two _upsert_batch calls"


# ──────────────────────────────────────────────────────────────────────────────
# REG-002: _delete_invalid must commit its deletes durably
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.regression
class TestReg002DeleteCommitsInternally:
    def _insert_committed_row(self, event_id: str) -> int:
        """Insert a row via a separate committed transaction; return its id."""
        conn = _fresh_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO raw_sensor_data
                        (event_id, device_id, room_id, ts, temperature,
                         humidity, motion, occupancy, raw_payload)
                    VALUES (%s, 'dev-reg', 'room-reg',
                            '2026-01-05T10:00:00+00:00', 21.5,
                            55.0, true, true, '{}')
                    RETURNING id
                    """,
                    (event_id,),
                )
                row_id: int = cur.fetchone()[0]
            conn.commit()
            return row_id
        finally:
            conn.close()

    def test_deleted_row_absent_on_fresh_connection_after_delete_conn_closed(
        self,
    ) -> None:
        """
        REG-002: _delete_invalid must call conn.commit() so that deletions
        survive after the deleting connection is discarded.  A brand-new
        connection must not see the deleted row.  If the internal commit is
        removed, rejected rows persist indefinitely and pollute every Analyze
        run.
        """
        row_id = self._insert_committed_row("reg-002-row")

        conn_delete = _fresh_conn()
        try:
            _delete_invalid(conn_delete, [row_id])
        finally:
            conn_delete.close()

        conn_read = _fresh_conn()
        try:
            with conn_read.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM raw_sensor_data WHERE id = %s", (row_id,))
                count: int = cur.fetchone()[0]
        finally:
            conn_read.close()

        assert count == 0, (
            "REG-002: deleted row still visible after deleting connection closed — "
            "_delete_invalid may not be committing"
        )


# ──────────────────────────────────────────────────────────────────────────────
# REG-003: API handlers must open and close their own connection
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.regression
class TestReg003ApiHandlerConnectionLifecycle:
    def test_get_patterns_repeated_invocations_do_not_raise(self) -> None:
        """
        REG-003: get_patterns opens and closes its own DB connection on every
        call.  Three consecutive invocations must all succeed without raising
        "connection already closed" or exhausting the connection pool.
        """
        event = _http_event({"job_id": "reg-003-patterns-job"})
        for _ in range(3):
            result = get_patterns(event, None)
            assert (
                result["statusCode"] == 200
            ), f"REG-003: get_patterns returned {result['statusCode']} on repeated call"

    def test_get_insights_repeated_invocations_do_not_raise(self) -> None:
        """
        REG-003: same lifecycle check for get_insights.
        """
        event = _http_event({"entity_type": "room", "entity_id": "reg-003-room"})
        for _ in range(3):
            result = get_insights(event, None)
            assert (
                result["statusCode"] == 200
            ), f"REG-003: get_insights returned {result['statusCode']} on repeated call"
