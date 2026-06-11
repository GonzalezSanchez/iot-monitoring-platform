import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

CATALOG = "p2c_dev"


def _connect():
    from databricks import sql

    host = os.environ["DATABRICKS_HOST"].removeprefix("https://")
    return sql.connect(
        server_hostname=host,
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )


def _rows_to_dicts(cursor) -> list[dict[str, Any]]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def get_anomalies(limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT
                    room_id,
                    sensor_type,
                    ROUND(value, 2)   AS value,
                    ROUND(z_score, 2) AS z_score,
                    ts
                FROM {CATALOG}.gold.fact_anomalies
                WHERE is_anomaly = true
                ORDER BY ts DESC
                LIMIT {limit}
            """)
            return _rows_to_dicts(cursor)


def get_summary() -> dict[str, Any]:
    with _connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT
                    COUNT(*)                                          AS total_events,
                    SUM(CASE WHEN is_anomaly THEN 1 ELSE 0 END)      AS total_anomalies,
                    MAX(ts)                                           AS latest_event_ts
                FROM {CATALOG}.gold.fact_anomalies
            """)
            summary = _rows_to_dicts(cursor)[0]

            cursor.execute(f"""
                SELECT MAX(_dbt_updated_at) AS last_dbt_run
                FROM {CATALOG}.gold.fact_patterns
            """)
            row = cursor.fetchone()
            summary["last_dbt_run"] = row[0] if row else None

            return summary


def get_rooms() -> list[dict[str, Any]]:
    with _connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT
                    r.room_id,
                    r.room_name,
                    r.floor,
                    r.capacity,
                    b.building_name,
                    b.city
                FROM {CATALOG}.gold.dim_rooms r
                JOIN {CATALOG}.gold.dim_buildings b ON r.building_id = b.building_id
                ORDER BY r.room_id
            """)
            return _rows_to_dicts(cursor)
