"""
Extract Lambda — project 2a Behavior Pattern Analyzer.

Reads sensor events from DynamoDB (project 1a: prod-SensorEvents) for a given
time window, deduplicates against raw_sensor_data, and inserts new rows.

Step Functions input — two supported formats:

  Scheduled (EventBridge → Step Functions):
    { "job_id": "<sfn-execution-name>", "days_back": 7 }
    → window is computed as [today - days_back, yesterday]

  Manual (ad-hoc trigger):
    { "job_id": "uuid", "start_date": "2026-01-01", "end_date": "2026-01-07" }

Output (passed to next state):
{
    "job_id":         "uuid",
    "start_date":     "2026-01-01",
    "end_date":       "2026-01-07",
    "extracted_count": 142
}
"""

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
import psycopg2.extensions
from shared.db import get_connection

log = logging.getLogger(__name__)
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def _scan_events(table: Any, start_iso: str, end_iso: str) -> list[dict]:
    """
    Scan DynamoDB for sensor events within [start_iso, end_iso] (date strings).
    Uses a FilterExpression on the 'timestamp' attribute.
    Returns a flat list of items.
    """
    start_dt = f"{start_iso}T00:00:00Z"
    end_dt = f"{end_iso}T23:59:59Z"

    items: list[dict] = []
    kwargs: dict = {
        "FilterExpression": "#ts BETWEEN :s AND :e",
        "ExpressionAttributeNames": {"#ts": "timestamp"},
        "ExpressionAttributeValues": {":s": start_dt, ":e": end_dt},
    }

    while True:
        response = table.scan(**kwargs)
        items.extend(response.get("Items", []))
        last = response.get("LastEvaluatedKey")
        if not last:
            break
        kwargs["ExclusiveStartKey"] = last

    return items


def _upsert_batch(conn: psycopg2.extensions.connection, rows: list[dict]) -> int:
    """
    Insert rows into raw_sensor_data, skipping duplicates (ON CONFLICT DO NOTHING).
    Returns the number of newly inserted rows.
    """
    if not rows:
        return 0

    sql = """
        INSERT INTO raw_sensor_data
            (event_id, device_id, room_id, ts,
             temperature, humidity, motion, occupancy, raw_payload)
        VALUES
            (%(event_id)s, %(device_id)s, %(room_id)s, %(ts)s,
             %(temperature)s, %(humidity)s, %(motion)s, %(occupancy)s, %(raw_payload)s)
        ON CONFLICT (event_id) DO NOTHING
    """
    inserted = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(sql, row)
            inserted += cur.rowcount
    conn.commit()
    return inserted


def _map_item(item: dict) -> dict:
    """Map a DynamoDB item to a raw_sensor_data row dict."""
    payload = item.get("payload", {})
    if isinstance(payload, str):
        payload = json.loads(payload)

    return {
        "event_id": item["event_id"],
        "device_id": item.get("device_id", "unknown"),
        "room_id": item.get("room_id", "unknown"),
        "ts": item.get("timestamp", item.get("ts")),  # Support both 'timestamp' and 'ts' keys
        "temperature": payload.get("temperature"),
        "humidity": payload.get("humidity"),
        "motion": payload.get("motion"),
        "occupancy": payload.get("occupancy"),
        "raw_payload": json.dumps(payload),
    }


def handler(event: dict, context: Any) -> dict:
    job_id = event["job_id"]

    # Resolve time window: explicit dates take priority, fall back to days_back
    if "start_date" in event and "end_date" in event:
        start_date = event["start_date"]
        end_date = event["end_date"]
    else:
        days_back = int(event.get("days_back", 7))
        today = datetime.now(tz=UTC).date()
        end_date = (today - timedelta(days=1)).isoformat()
        start_date = (today - timedelta(days=days_back)).isoformat()

    log.info("Extract job_id=%s  window=%s → %s", job_id, start_date, end_date)

    table_name = os.environ["DYNAMODB_TABLE_EVENTS"]
    region = os.getenv("AWS_REGION", "eu-central-1")

    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    items = _scan_events(table, start_date, end_date)
    log.info("Scanned %d items from DynamoDB", len(items))

    rows = [_map_item(item) for item in items]

    conn = get_connection()
    try:
        inserted = _upsert_batch(conn, rows)
    finally:
        conn.close()

    log.info("Inserted %d new rows into raw_sensor_data", inserted)

    return {
        "job_id": job_id,
        "start_date": start_date,
        "end_date": end_date,
        "extracted_count": inserted,
    }
