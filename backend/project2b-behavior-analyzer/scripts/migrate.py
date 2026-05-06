#!/usr/bin/env python3
"""
DB migration script for project 2b — Behavior Pattern Analyzer.

Creates (or updates) the core tables in PostgreSQL (Docker Compose):
  - raw_sensor_data        : partitioned by month, ingested from S3 Parquet
  - processed_sensor_data  : normalized output from transform job
  - patterns               : detected behavioral patterns
  - anomalies              : detected anomalies per entity

Idempotent — safe to run multiple times (CREATE TABLE IF NOT EXISTS).
Reads DB_* env vars from .env (loaded via python-dotenv).

Usage:
    python scripts/migrate.py
"""

import logging
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# SQL
# ──────────────────────────────────────────────────────────────────────────────

DDL_STATEMENTS = [
    # pgvector — needed for project 4 RAG queries over patterns/anomalies
    "CREATE EXTENSION IF NOT EXISTS vector",
    # Raw readings ingested from S3 Parquet (originally from DynamoDB SensorEvents)
    # Partitioned by month — inspired by https://gitlab.com/dmorel69/fastapi-dbuploader
    """
    CREATE TABLE IF NOT EXISTS raw_sensor_data (
        id            BIGSERIAL,
        event_id      TEXT             NOT NULL,
        device_id     TEXT             NOT NULL,
        room_id       TEXT             NOT NULL,
        ts            TIMESTAMPTZ      NOT NULL,
        temperature   DOUBLE PRECISION,
        humidity      DOUBLE PRECISION,
        motion        BOOLEAN,
        occupancy     BOOLEAN,
        raw_payload   JSONB            NOT NULL,
        ingested_at   TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
        processed     BOOLEAN          NOT NULL DEFAULT FALSE,
        PRIMARY KEY (id, ts)
    ) PARTITION BY RANGE (ts)
    """,
    "CREATE INDEX IF NOT EXISTS idx_raw_sensor_data_room_id   ON raw_sensor_data (room_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_sensor_data_event_id  ON raw_sensor_data (event_id)",
    # Partial index — only unprocessed rows, keeps the index small
    "CREATE INDEX IF NOT EXISTS idx_raw_sensor_data_unprocessed"
    " ON raw_sensor_data (processed) WHERE processed = FALSE",
    # Normalized output from transform job
    """
    CREATE TABLE IF NOT EXISTS processed_sensor_data (
        id            BIGSERIAL        PRIMARY KEY,
        event_id      TEXT             NOT NULL UNIQUE,
        device_id     TEXT             NOT NULL,
        room_id       TEXT             NOT NULL,
        ts            TIMESTAMPTZ      NOT NULL,
        temperature_c DOUBLE PRECISION,
        humidity_pct  DOUBLE PRECISION,
        motion        BOOLEAN,
        occupancy     BOOLEAN,
        processed_at  TIMESTAMPTZ      NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_processed_room_id ON processed_sensor_data (room_id)",
    "CREATE INDEX IF NOT EXISTS idx_processed_ts      ON processed_sensor_data (ts)",
    # Behavioral patterns detected by PySpark analyze job
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
    # Anomalies detected by PySpark analyze job
    # severity: 'medium' (z >= 3) | 'high' (z >= 5) — min. 4 measurements required
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

# ──────────────────────────────────────────────────────────────────────────────
# Connection
# ──────────────────────────────────────────────────────────────────────────────


def get_connection_params() -> dict:
    missing = [v for v in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not os.getenv(v)]
    if missing:
        log.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)

    return {
        "host": os.environ["DB_HOST"],
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Migration
# ──────────────────────────────────────────────────────────────────────────────


def run_migrations(params: dict) -> None:
    log.info(
        "Connecting to %s:%s/%s as %s",
        params["host"],
        params["port"],
        params["dbname"],
        params["user"],
    )

    try:
        conn = psycopg2.connect(**params)
    except psycopg2.OperationalError as exc:
        log.error("Connection failed: %s", exc)
        sys.exit(1)

    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            for statement in DDL_STATEMENTS:
                label = statement.strip().splitlines()[0][:60]
                log.debug("Executing: %s ...", label)
                cur.execute(statement)
        conn.commit()
        log.info("Migration complete — all tables and indexes are up to date.")
    except Exception as exc:
        conn.rollback()
        log.error("Migration failed, rolled back: %s", exc)
        sys.exit(1)
    finally:
        conn.close()


def main() -> None:
    params = get_connection_params()
    run_migrations(params)


if __name__ == "__main__":
    main()
