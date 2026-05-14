#!/usr/bin/env python3
"""
seed_rooms.py — populate the rooms table with building and location data.

Rooms correspond to the room_ids used in seed_dynamodb.py.
Coordinates are fictional but realistic — placed in an office park near Antwerp.

Note: in a production system, building and location metadata would be managed
by the device registry in project 1a (POST /rooms endpoint). For this portfolio
the rooms table is seeded directly to keep the projects self-contained.

Credential resolution (in order):
  1. AWS (production)  : reads SECRETS_MANAGER_SECRET_NAME from environment
  2. Local (dev/CI)    : reads DB_* env vars from .env

Usage:
    python scripts/seed_rooms.py
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

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOMS = [
    {
        "room_id": "conference-a1",
        "building_id": "building-a",
        "building_name": "Building A — Hoofdgebouw",
        "floor": 1,
        "lat": 51.2195,
        "lon": 4.4024,
    },
    {
        "room_id": "conference-b2",
        "building_id": "building-b",
        "building_name": "Building B — Vergadercentrum",
        "floor": 2,
        "lat": 51.2201,
        "lon": 4.4038,
    },
    {
        "room_id": "server-room-e5",
        "building_id": "building-e",
        "building_name": "Building E — Datacenter",
        "floor": 0,
        "lat": 51.2189,
        "lon": 4.4015,
    },
]


def _get_secret(secret_id: str, region: str) -> dict:
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_id)
    return json.loads(response["SecretString"])


def get_connection_params() -> dict:
    secret_name = os.getenv("SECRETS_MANAGER_SECRET_NAME")
    if secret_name:
        region = os.getenv("AWS_REGION", "eu-central-1")
        try:
            main_secret = _get_secret(secret_name, region)
            master_secret = _get_secret(main_secret["master_secret_arn"], region)
        except ClientError as exc:
            log.error("Failed to fetch credentials from Secrets Manager: %s", exc)
            sys.exit(1)
        return {
            "host": main_secret["host"],
            "port": int(main_secret["port"]),
            "dbname": main_secret["dbname"],
            "user": main_secret["username"],
            "password": master_secret["password"],
        }

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


def seed(conn: psycopg2.extensions.connection) -> None:
    sql = """
        INSERT INTO rooms (room_id, building_id, building_name, floor, lat, lon)
        VALUES (%(room_id)s, %(building_id)s, %(building_name)s, %(floor)s, %(lat)s, %(lon)s)
        ON CONFLICT (room_id) DO UPDATE
            SET building_id   = EXCLUDED.building_id,
                building_name = EXCLUDED.building_name,
                floor         = EXCLUDED.floor,
                lat           = EXCLUDED.lat,
                lon           = EXCLUDED.lon
    """
    with conn.cursor() as cur:
        for room in ROOMS:
            cur.execute(sql, room)
            log.info("Upserted room: %s (%s)", room["room_id"], room["building_name"])
    conn.commit()
    log.info("Seeded %d rooms.", len(ROOMS))


def main() -> None:
    params = get_connection_params()
    try:
        conn = psycopg2.connect(**params)
    except psycopg2.OperationalError as exc:
        log.error("Connection failed: %s", exc)
        sys.exit(1)
    try:
        seed(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
