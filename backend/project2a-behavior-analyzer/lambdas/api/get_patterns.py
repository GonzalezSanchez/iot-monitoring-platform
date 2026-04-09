"""
GET /analyze/patterns/{job_id}

Returns all patterns detected for a given ETL job.

Response 200:
  { "job_id": "...", "patterns": [ { ... }, ... ] }
"""

import json
import logging
import os

from shared.db import get_connection

log = logging.getLogger(__name__)
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))

_SQL = """
    SELECT job_id, entity_type, entity_id, pattern_type, data, period_start, period_end
    FROM   patterns
    WHERE  job_id = %s
    ORDER  BY entity_id, pattern_type
"""


def handler(event: dict, context) -> dict:
    job_id = event["pathParameters"]["job_id"]
    log.info("GET patterns job_id=%s", job_id)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_SQL, (job_id,))
            cols = (
                "job_id",
                "entity_type",
                "entity_id",
                "pattern_type",
                "data",
                "period_start",
                "period_end",
            )
            patterns = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()

    return {
        "statusCode": 200,
        "body": json.dumps({"job_id": job_id, "patterns": patterns}, default=str),
    }
