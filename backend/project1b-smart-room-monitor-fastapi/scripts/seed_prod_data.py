"""
Script: seed_prod_data.py
Populates the production DynamoDB tables with realistic demo data.

Reads credentials from .env.prod (must exist in project1b root).
Run from the project1b directory:
    python scripts/seed_prod_data.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import cast

import boto3
from dotenv import load_dotenv

# Load .env.prod from project1b root
env_path = Path(__file__).parent.parent / ".env.prod"
if not env_path.exists():
    print(f"ERROR: {env_path} not found. Create it with AWS credentials first.")
    sys.exit(1)
load_dotenv(env_path)

dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.environ["AWS_REGION"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    # No endpoint_url → hits real AWS
)

rooms_table = dynamodb.Table(os.environ["DYNAMODB_TABLE_ROOMS"])
events_table = dynamodb.Table(os.environ["DYNAMODB_TABLE_EVENTS"])

now = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

ROOMS = [
    {
        "room_id": "conference-a1",
        "name": "Conference Room A1",
        "status": "active",
        "last_update": now.isoformat(),
        "current_state": {
            "temperature": Decimal("21.5"),
            "humidity": Decimal("48.0"),
            "occupancy": 6,
            "motion": True,
        },
        "alert_count_24h": 0,
    },
    {
        "room_id": "conference-b2",
        "name": "Conference Room B2",
        "status": "warning",
        "last_update": (now - timedelta(minutes=5)).isoformat(),
        "current_state": {
            "temperature": Decimal("27.8"),
            "humidity": Decimal("62.0"),
            "occupancy": 2,
            "motion": True,
        },
        "alert_count_24h": 2,
    },
    {
        "room_id": "meeting-room-c3",
        "name": "Meeting Room C3",
        "status": "active",
        "last_update": (now - timedelta(minutes=12)).isoformat(),
        "current_state": {
            "temperature": Decimal("20.0"),
            "humidity": Decimal("44.5"),
            "occupancy": 0,
            "motion": False,
        },
        "alert_count_24h": 0,
    },
    {
        "room_id": "lab-d4",
        "name": "Lab D4",
        "status": "alert",
        "last_update": (now - timedelta(minutes=2)).isoformat(),
        "current_state": {
            "temperature": Decimal("32.1"),
            "humidity": Decimal("71.0"),
            "occupancy": 1,
            "motion": True,
        },
        "alert_count_24h": 5,
    },
]

# ---------------------------------------------------------------------------
# Events (recent history per room)
# ---------------------------------------------------------------------------

EVENTS = [
    # conference-a1 — stable, normal readings
    {
        "room_id": "conference-a1",
        "sensor_type": "temperature",
        "value": Decimal("21.5"),
        "unit": "°C",
        "status": "normal",
        "minutes_ago": 2,
    },
    {
        "room_id": "conference-a1",
        "sensor_type": "humidity",
        "value": Decimal("48.0"),
        "unit": "%",
        "status": "normal",
        "minutes_ago": 2,
    },
    {
        "room_id": "conference-a1",
        "sensor_type": "occupancy",
        "value": Decimal("6"),
        "unit": "people",
        "status": "normal",
        "minutes_ago": 3,
    },
    {
        "room_id": "conference-a1",
        "sensor_type": "motion",
        "value": Decimal("1"),
        "unit": "boolean",
        "status": "normal",
        "minutes_ago": 3,
    },
    # conference-b2 — temperature warning
    {
        "room_id": "conference-b2",
        "sensor_type": "temperature",
        "value": Decimal("25.1"),
        "unit": "°C",
        "status": "normal",
        "minutes_ago": 30,
    },
    {
        "room_id": "conference-b2",
        "sensor_type": "temperature",
        "value": Decimal("26.4"),
        "unit": "°C",
        "status": "warning",
        "minutes_ago": 15,
    },
    {
        "room_id": "conference-b2",
        "sensor_type": "temperature",
        "value": Decimal("27.8"),
        "unit": "°C",
        "status": "warning",
        "minutes_ago": 5,
    },
    {
        "room_id": "conference-b2",
        "sensor_type": "humidity",
        "value": Decimal("62.0"),
        "unit": "%",
        "status": "warning",
        "minutes_ago": 5,
    },
    # meeting-room-c3 — empty, quiet
    {
        "room_id": "meeting-room-c3",
        "sensor_type": "temperature",
        "value": Decimal("20.0"),
        "unit": "°C",
        "status": "normal",
        "minutes_ago": 12,
    },
    {
        "room_id": "meeting-room-c3",
        "sensor_type": "occupancy",
        "value": Decimal("0"),
        "unit": "people",
        "status": "normal",
        "minutes_ago": 12,
    },
    {
        "room_id": "meeting-room-c3",
        "sensor_type": "motion",
        "value": Decimal("0"),
        "unit": "boolean",
        "status": "normal",
        "minutes_ago": 12,
    },
    # lab-d4 — high temp alert
    {
        "room_id": "lab-d4",
        "sensor_type": "temperature",
        "value": Decimal("28.5"),
        "unit": "°C",
        "status": "warning",
        "minutes_ago": 60,
    },
    {
        "room_id": "lab-d4",
        "sensor_type": "temperature",
        "value": Decimal("30.2"),
        "unit": "°C",
        "status": "alert",
        "minutes_ago": 30,
    },
    {
        "room_id": "lab-d4",
        "sensor_type": "temperature",
        "value": Decimal("32.1"),
        "unit": "°C",
        "status": "alert",
        "minutes_ago": 2,
    },
    {
        "room_id": "lab-d4",
        "sensor_type": "humidity",
        "value": Decimal("71.0"),
        "unit": "%",
        "status": "alert",
        "minutes_ago": 2,
    },
    {
        "room_id": "lab-d4",
        "sensor_type": "motion",
        "value": Decimal("1"),
        "unit": "boolean",
        "status": "normal",
        "minutes_ago": 2,
    },
]


def seed_rooms() -> None:
    print("\n--- Seeding rooms ---")
    for room in ROOMS:
        rooms_table.put_item(Item=room)
        print(f"  ✓ {room['room_id']} ({room['status']})")


def seed_events() -> None:
    print("\n--- Seeding events ---")
    for ev in EVENTS:
        ts = now - timedelta(minutes=cast(int, ev["minutes_ago"]))
        item = {
            "room_id": ev["room_id"],
            "timestamp": ts.isoformat(),
            "event_id": f"{ev['room_id']}_{ts.timestamp()}",
            "sensor_type": ev["sensor_type"],
            "value": ev["value"],
            "unit": ev["unit"],
            "status": ev["status"],
        }
        events_table.put_item(Item=item)
        print(f"  ✓ {ev['room_id']} / {ev['sensor_type']} = {ev['value']} ({ev['status']})")


if __name__ == "__main__":
    print(f"Seeding prod tables in region {os.environ['AWS_REGION']}")
    print(f"  Rooms table : {os.environ['DYNAMODB_TABLE_ROOMS']}")
    print(f"  Events table: {os.environ['DYNAMODB_TABLE_EVENTS']}")
    seed_rooms()
    seed_events()
    print("\nDone.")
