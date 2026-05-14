"""
Transform Lambda — project 2a Behavior Pattern Analyzer.

Reads unprocessed rows from raw_sensor_data (where ingested_at is within the
job window), validates and cleans them, and marks them processed=true.

No separate output table — transformation is in-place so the Analyze Lambda
can join on the same rows with confidence they are clean.

Step Functions input (from Extract output):
{
    "job_id":          "uuid",
    "start_date":      "2026-01-01",
    "end_date":        "2026-01-07",
    "extracted_count": 142
}

Output:
{
    "job_id":            "uuid",
    "start_date":        "2026-01-01",
    "end_date":          "2026-01-07",
    "transformed_count": 138,  # rows that passed validation
    "rejected_count":    4     # rows dropped (null ts, missing device_id, …)
}
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

import psycopg2.extensions
from shared.db import get_connection

log = logging.getLogger(__name__)
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# Plausible sensor value ranges — readings outside are rejected
TEMP_MIN, TEMP_MAX = -20.0, 60.0
HUMIDITY_MIN, HUMIDITY_MAX = 0.0, 100.0


@dataclass
class RawRow:
    id: int
    event_id: str
    device_id: str
    room_id: str
    ts: object
    temperature: float | None
    humidity: float | None
    motion: bool | None
    occupancy: bool | None


def _fetch_unprocessed(
    conn: psycopg2.extensions.connection, start_date: str, end_date: str
) -> list[RawRow]:
    sql = """
        SELECT id, event_id, device_id, room_id, ts,
               temperature, humidity, motion, occupancy
        FROM   raw_sensor_data
        WHERE  ts BETWEEN %s AND %s
          AND  ingested_at IS NOT NULL
    """
    with conn.cursor() as cur:
        cur.execute(sql, (f"{start_date}T00:00:00Z", f"{end_date}T23:59:59Z"))
        return [RawRow(*row) for row in cur.fetchall()]


def _is_valid(row: RawRow) -> bool:
    if not row.device_id or not row.room_id or row.ts is None:
        return False
    if row.temperature is None or not (TEMP_MIN <= row.temperature <= TEMP_MAX):
        return False
    if row.humidity is None or not (HUMIDITY_MIN <= row.humidity <= HUMIDITY_MAX):
        return False
    return True


def _delete_invalid(conn: psycopg2.extensions.connection, ids: list[int]) -> None:
    if not ids:
        return
    with conn.cursor() as cur:
        cur.execute("DELETE FROM raw_sensor_data WHERE id = ANY(%s)", (ids,))
    conn.commit()


def handler(event: dict, context: Any) -> dict:
    job_id = event["job_id"]
    start_date = event["start_date"]
    end_date = event["end_date"]

    log.info("Transform job_id=%s  window=%s → %s", job_id, start_date, end_date)

    conn = get_connection()
    try:
        rows = _fetch_unprocessed(conn, start_date, end_date)
        log.info("Fetched %d raw rows", len(rows))

        valid_ids: list[int] = []
        invalid_ids: list[int] = []

        for row in rows:
            if _is_valid(row):
                valid_ids.append(row.id)
            else:
                log.debug("Rejecting row id=%d event_id=%s", row.id, row.event_id)
                invalid_ids.append(row.id)

        _delete_invalid(conn, invalid_ids)
    finally:
        conn.close()

    log.info(
        "Transform complete: %d valid, %d rejected",
        len(valid_ids),
        len(invalid_ids),
    )

    return {
        "job_id": job_id,
        "start_date": start_date,
        "end_date": end_date,
        "transformed_count": len(valid_ids),
        "rejected_count": len(invalid_ids),
    }
