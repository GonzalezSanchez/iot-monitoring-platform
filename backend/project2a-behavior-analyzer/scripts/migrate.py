#!/usr/bin/env python3
"""
DB migration script for project 2a — Behavior Pattern Analyzer.

Creates (or updates) the three core tables in Aurora PostgreSQL:
  - raw_sensor_data   : ingested readings from DynamoDB SensorEvents
  - patterns          : detected behavioral patterns (occupancy, temperature trends)
  - anomalies         : detected anomalies per entity

Idempotent — safe to run multiple times (CREATE TABLE IF NOT EXISTS).

Credential resolution (in order):
  1. AWS (production)  : reads SECRETS_MANAGER_SECRET_NAME from environment,
                         fetches connection details + Aurora-managed password
  2. Local (dev/CI)    : reads DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
                         from .env (loaded via python-dotenv)

Usage:
    python scripts/migrate.py
"""

import json
import logging
import os
import sys

import boto3
import psycopg2
from botocore.exceptions import ClientError
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
    # Raw readings ingested from DynamoDB SensorEvents (project 1a)
    """
    CREATE TABLE IF NOT EXISTS raw_sensor_data (
        id            BIGSERIAL     PRIMARY KEY,
        event_id      TEXT          NOT NULL UNIQUE,
        device_id     TEXT          NOT NULL,
        room_id       TEXT          NOT NULL,
        ts            TIMESTAMPTZ   NOT NULL,
        temperature   DOUBLE PRECISION,
        humidity      DOUBLE PRECISION,
        motion        BOOLEAN,
        occupancy     BOOLEAN,
        raw_payload   JSONB         NOT NULL,
        ingested_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_raw_sensor_data_room_id ON raw_sensor_data (room_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_sensor_data_ts     ON raw_sensor_data (ts)",
    # Behavioral patterns detected by the Analyze Lambda
    """
    CREATE TABLE IF NOT EXISTS patterns (
        id            BIGSERIAL     PRIMARY KEY,
        job_id        TEXT          NOT NULL,
        entity_type   TEXT          NOT NULL,   -- 'room' | 'device'
        entity_id     TEXT          NOT NULL,
        pattern_type  TEXT          NOT NULL,   -- 'occupancy_schedule' | 'temperature_trend' | ...
        period_start  TIMESTAMPTZ   NOT NULL,
        period_end    TIMESTAMPTZ   NOT NULL,
        data          JSONB         NOT NULL,
        created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_patterns_entity ON patterns (entity_type, entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_patterns_job_id ON patterns (job_id)",
    # Anomalies detected by the Analyze Lambda
    """
    CREATE TABLE IF NOT EXISTS anomalies (
        id            BIGSERIAL     PRIMARY KEY,
        job_id        TEXT          NOT NULL,
        entity_type   TEXT          NOT NULL,   -- 'room' | 'device'
        entity_id     TEXT          NOT NULL,
        anomaly_type  TEXT          NOT NULL,   -- 'unusual_activity' | 'temperature_spike' | ...
        detected_at   TIMESTAMPTZ   NOT NULL,
        severity      TEXT          NOT NULL,   -- 'low' | 'medium' | 'high'
        data          JSONB         NOT NULL,
        created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_anomalies_entity ON anomalies (entity_type, entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_anomalies_job_id ON anomalies (job_id)",
]


# ──────────────────────────────────────────────────────────────────────────────
# Credential resolution
# ──────────────────────────────────────────────────────────────────────────────


def _get_secret(secret_id: str, region: str) -> dict:
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_id)
    return json.loads(response["SecretString"])


def get_connection_params() -> dict:
    """
    Returns a dict with keys: host, port, dbname, user, password.

    AWS path  : reads SECRETS_MANAGER_SECRET_NAME, then fetches the
                Aurora-managed password from master_secret_arn.
    Local path: reads DB_* env vars (populated from .env).
    """
    secret_name = os.getenv("SECRETS_MANAGER_SECRET_NAME")

    if secret_name:
        log.info("Fetching credentials from Secrets Manager: %s", secret_name)
        region = os.getenv("AWS_REGION", "eu-central-1")

        try:
            main_secret = _get_secret(secret_name, region)
        except ClientError as exc:
            log.error("Failed to fetch main secret '%s': %s", secret_name, exc)
            sys.exit(1)

        master_arn = main_secret.get("master_secret_arn")
        if not master_arn:
            log.error("Secret '%s' has no 'master_secret_arn' key.", secret_name)
            sys.exit(1)

        try:
            master_secret = _get_secret(master_arn, region)
        except ClientError as exc:
            log.error("Failed to fetch master password secret: %s", exc)
            sys.exit(1)

        return {
            "host": main_secret["host"],
            "port": int(main_secret["port"]),
            "dbname": main_secret["dbname"],
            "user": main_secret["username"],
            "password": master_secret["password"],
        }

    # Local dev — read from .env
    log.info("Using local DB credentials from environment / .env")
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
