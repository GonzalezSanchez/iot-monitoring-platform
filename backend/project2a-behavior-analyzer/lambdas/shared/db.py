"""
Shared database connection helper for project 2a Lambdas.

Resolves credentials (Secrets Manager in AWS, .env locally) and returns
a psycopg2 connection.  Connection is not pooled — each Lambda invocation
opens and closes its own connection.
"""

import json
import logging
import os
from typing import Any

import boto3
import psycopg2
import psycopg2.extensions
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)


def _get_secret(secret_id: str, region: str) -> dict[str, Any]:
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_id)
    result: dict[str, Any] = json.loads(response["SecretString"])
    return result


def _connection_params() -> dict:
    """
    Return psycopg2-compatible connection kwargs.

    AWS  : SECRETS_MANAGER_SECRET_NAME is set → fetch from Secrets Manager
    Local: DB_HOST / DB_NAME / DB_USER / DB_PASSWORD from environment
    """
    secret_name = os.getenv("SECRETS_MANAGER_SECRET_NAME")

    if secret_name:
        region = os.getenv("AWS_REGION", "eu-central-1")
        try:
            main = _get_secret(secret_name, region)
            master = _get_secret(main["master_secret_arn"], region)
        except ClientError as exc:
            log.error("Secrets Manager error: %s", exc)
            raise

        return {
            "host": main["host"],
            "port": int(main["port"]),
            "dbname": main["dbname"],
            "user": main["username"],
            "password": master["password"],
        }

    return {
        "host": os.environ["DB_HOST"],
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }


def get_connection() -> psycopg2.extensions.connection:
    params = _connection_params()
    log.debug("Connecting to %s:%s/%s", params["host"], params["port"], params["dbname"])
    return psycopg2.connect(**params)
