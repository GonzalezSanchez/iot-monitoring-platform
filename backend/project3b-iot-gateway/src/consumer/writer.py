"""Idempotent writes to the shared prod-SensorEvents / prod-RoomStatus tables.

boto3 is synchronous — the consumer loop calls these via asyncio.to_thread.

The RoomStatus refresh is deliberately mechanical (current sensor values +
last_update, create-if-missing): anomaly detection and room status calculation
are project 1b's business logic and are not duplicated here.
"""

from decimal import Decimal
from typing import Any, Dict, List

import boto3

from consumer import config

# current_state field per sensor type, mirroring the 1b RoomState model
_STATE_CASTS = {
    "temperature": lambda v: Decimal(str(v)),
    "humidity": lambda v: Decimal(str(v)),
    "occupancy": lambda v: int(v),
    "motion": lambda v: bool(v),
}


def _dynamodb():
    return boto3.resource("dynamodb", region_name=config.AWS_REGION)


def write_events(items: List[Dict[str, Any]]) -> None:
    """put_item per item — (room_id, timestamp) keys are deterministic, so
    redelivery overwrites the same items instead of duplicating them."""
    table = _dynamodb().Table(config.SENSOR_EVENTS_TABLE)
    for item in items:
        table.put_item(Item=item)


def refresh_room(items: List[Dict[str, Any]]) -> None:
    """Update the room's current_state and last_update from the normalised items."""
    room_id = items[0]["room_id"]
    last_update = max(item["timestamp"] for item in items)
    table = _dynamodb().Table(config.ROOM_STATUS_TABLE)

    existing = table.get_item(Key={"room_id": room_id}).get("Item")
    room: Dict[str, Any] = existing or {
        "room_id": room_id,
        "name": f"Room {room_id}",
        "status": "active",
        "current_state": {},
        "alert_count_24h": 0,
    }

    state = dict(room.get("current_state") or {})
    for item in items:
        state[item["sensor_type"]] = _STATE_CASTS[item["sensor_type"]](item["value"])
    room["current_state"] = state
    room["last_update"] = last_update

    table.put_item(Item=room)
