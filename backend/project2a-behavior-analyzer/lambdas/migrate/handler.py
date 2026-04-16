"""
Migrate Lambda — project 2a Behavior Pattern Analyzer.

Creates (or updates) the three core tables in Aurora PostgreSQL:
  - raw_sensor_data : ingested readings from DynamoDB SensorEvents
  - patterns        : detected behavioral patterns
  - anomalies       : detected anomalies per entity

Idempotent — safe to invoke multiple times (CREATE TABLE IF NOT EXISTS).

Invoke once after first deploy:
  aws lambda invoke --function-name p2a-prod-migrate \\
    --region eu-central-1 --log-type Tail /tmp/migrate-output.json
  cat /tmp/migrate-output.json
"""

import logging
import os
from typing import Any

from shared.db import get_connection

log = logging.getLogger(__name__)
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS raw_sensor_data (
        id            BIGSERIAL        PRIMARY KEY,
        event_id      TEXT             NOT NULL UNIQUE,
        device_id     TEXT             NOT NULL,
        room_id       TEXT             NOT NULL,
        ts            TIMESTAMPTZ      NOT NULL,
        temperature   DOUBLE PRECISION,
        humidity      DOUBLE PRECISION,
        motion        BOOLEAN,
        occupancy     BOOLEAN,
        raw_payload   JSONB            NOT NULL,
        ingested_at   TIMESTAMPTZ      NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_raw_sensor_data_room_id ON raw_sensor_data (room_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_sensor_data_ts     ON raw_sensor_data (ts)",
    """
    CREATE TABLE IF NOT EXISTS patterns (
        id            BIGSERIAL        PRIMARY KEY,
        job_id        TEXT             NOT NULL,
        entity_type   TEXT             NOT NULL,
        entity_id     TEXT             NOT NULL,
        pattern_type  TEXT             NOT NULL,
        period_start  TIMESTAMPTZ      NOT NULL,
        period_end    TIMESTAMPTZ      NOT NULL,
        data          JSONB            NOT NULL,
        created_at    TIMESTAMPTZ      NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_patterns_entity ON patterns (entity_type, entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_patterns_job_id ON patterns (job_id)",
    """
    CREATE TABLE IF NOT EXISTS anomalies (
        id            BIGSERIAL        PRIMARY KEY,
        job_id        TEXT             NOT NULL,
        entity_type   TEXT             NOT NULL,
        entity_id     TEXT             NOT NULL,
        anomaly_type  TEXT             NOT NULL,
        detected_at   TIMESTAMPTZ      NOT NULL,
        severity      TEXT             NOT NULL,
        data          JSONB            NOT NULL,
        created_at    TIMESTAMPTZ      NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_anomalies_entity ON anomalies (entity_type, entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_anomalies_job_id ON anomalies (job_id)",
]


def handler(event: dict, context: Any) -> dict:
    log.info("Starting database migration...")

    conn = get_connection()
    conn.autocommit = False

    executed = 0
    try:
        with conn.cursor() as cur:
            for statement in DDL_STATEMENTS:
                label = statement.strip().splitlines()[0][:60]
                log.info("Executing: %s ...", label)
                cur.execute(statement)
                executed += 1
        conn.commit()
    except Exception as exc:
        conn.rollback()
        log.error("Migration failed, rolled back: %s", exc)
        return {"status": "error", "message": str(exc)}
    finally:
        conn.close()

    log.info("Migration complete — %d statements executed.", executed)
    return {"status": "ok", "statements_executed": executed}
