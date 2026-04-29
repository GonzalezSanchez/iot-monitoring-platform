"""
POST /analyze/patterns

Starts a Step Functions ETL execution for a given time window.

Request body (JSON):
  { "days_back": 7 }   ← optional, default 7

Response 202:
  { "execution_arn": "arn:...", "job_id": "<uuid-part>" }

Response 400:
  { "error": "..." }
"""

import json
import logging
import os
import uuid
from typing import Any

import boto3

log = logging.getLogger(__name__)
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def handler(event: dict, context: Any) -> dict:
    raw_body = event.get("body")
    if not raw_body:
        return {"statusCode": 400, "body": json.dumps({"error": "request body is required"})}

    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError):
        return {"statusCode": 400, "body": json.dumps({"error": "invalid JSON body"})}

    days_back = int(body.get("days_back", 7))
    job_id = str(uuid.uuid4())

    state_machine_arn = os.environ["STATE_MACHINE_ARN"]
    sfn = boto3.client("stepfunctions", region_name=os.getenv("AWS_REGION", "eu-central-1"))

    response = sfn.start_execution(
        stateMachineArn=state_machine_arn,
        name=job_id,
        input=json.dumps({"job_id": job_id, "days_back": days_back}),
    )

    log.info("Started execution job_id=%s  arn=%s", job_id, response["executionArn"])

    return {
        "statusCode": 202,
        "body": json.dumps({"job_id": job_id, "execution_arn": response["executionArn"]}),
    }
