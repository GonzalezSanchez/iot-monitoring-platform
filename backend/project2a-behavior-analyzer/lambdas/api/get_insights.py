"""
GET /insights/{entity_type}/{entity_id}

Returns all patterns and anomalies for a given entity (room or device).

Response 200:
  {
    "entity_type": "room",
    "entity_id":   "room-a",
    "patterns":    [ { ... }, ... ],
    "anomalies":   [ { ... }, ... ]
  }
"""

import json
import logging
import os
from typing import Any

from shared.db import get_connection

log = logging.getLogger(__name__)
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))

_SQL_PATTERNS = """
    SELECT job_id, entity_type, entity_id, pattern_type, data, period_start, period_end
    FROM   patterns
    WHERE  entity_type = %s AND entity_id = %s
    ORDER  BY period_start DESC
"""

_SQL_ANOMALIES = """
    SELECT job_id, entity_type, entity_id, anomaly_type, detected_at, severity, data
    FROM   anomalies
    WHERE  entity_type = %s AND entity_id = %s
    ORDER  BY detected_at DESC
"""


def handler(event: dict, context: Any) -> dict:
    entity_type = event["pathParameters"]["entity_type"]
    entity_id = event["pathParameters"]["entity_id"]
    log.info("GET insights entity_type=%s entity_id=%s", entity_type, entity_id)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_SQL_PATTERNS, (entity_type, entity_id))
            pattern_cols = (
                "job_id",
                "entity_type",
                "entity_id",
                "pattern_type",
                "data",
                "period_start",
                "period_end",
            )
            patterns = [dict(zip(pattern_cols, row)) for row in cur.fetchall()]

            cur.execute(_SQL_ANOMALIES, (entity_type, entity_id))
            anomaly_cols = (
                "job_id",
                "entity_type",
                "entity_id",
                "anomaly_type",
                "detected_at",
                "severity",
                "data",
            )
            anomalies = [dict(zip(anomaly_cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "patterns": patterns,
                "anomalies": anomalies,
            },
            default=str,
        ),
    }
