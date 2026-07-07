"""Gateway message → shared prod-SensorEvents contract (docs/project3-prd.md §7 3b-2).

Pure functions, no I/O. The output item shape is the golden contract project 1b
writes (`SensorEvent.to_dynamodb_item()` in project1b): room_id + timestamp key,
event_id, sensor_type, value (Decimal), unit, status.

Idempotency by construction: event_id is a uuid5 of message_id + sensor_type and
the sort-key timestamp gets a deterministic per-sensor microsecond offset, so
redelivering the same gateway message produces byte-identical items (DynamoDB
put_item then overwrites instead of duplicating).
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

# Mirrors the sensor types and units of the 1b SensorEvent model
SENSOR_UNITS = {
    "temperature": "°C",
    "humidity": "%",
    "occupancy": "people",
    "motion": "boolean",
}

_EVENT_ID_NAMESPACE = uuid.UUID("b56742a4-0000-4000-8000-3b0000000001")


class NormalizationError(Exception):
    """Message cannot be normalised — goes to the DLQ with this reason."""


def normalize(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fan a gateway message out to one shared-contract item per known sensor field."""
    for field in ("message_id", "device_id", "payload", "timestamp"):
        if not event.get(field):
            raise NormalizationError(f"malformed: missing field '{field}'")
    payload = event["payload"]
    if not isinstance(payload, dict):
        raise NormalizationError("malformed: payload is not an object")

    room_id = event.get("location")
    if not room_id:
        raise NormalizationError(
            f"unknown room mapping: device '{event['device_id']}' has no location metadata"
        )

    try:
        base_ts = datetime.fromisoformat(str(event["timestamp"]).replace("Z", "+00:00"))
    except ValueError:
        raise NormalizationError(f"malformed: unparseable timestamp '{event['timestamp']}'")

    readings = {k: v for k, v in payload.items() if k in SENSOR_UNITS}
    if not readings:
        raise NormalizationError(
            f"no known sensor fields in payload (got: {sorted(payload)})"
        )

    items = []
    for offset, (sensor_type, value) in enumerate(sorted(readings.items())):
        if isinstance(value, bool):
            value = float(value)
        if not isinstance(value, (int, float)):
            raise NormalizationError(f"malformed: non-numeric value for '{sensor_type}'")
        items.append(
            {
                "room_id": room_id,
                # deterministic per-sensor offset keeps the (room_id, timestamp)
                # key unique within one fanned-out message
                "timestamp": (base_ts + timedelta(microseconds=offset)).isoformat(),
                "event_id": str(
                    uuid.uuid5(_EVENT_ID_NAMESPACE, f"{event['message_id']}:{sensor_type}")
                ),
                "sensor_type": sensor_type,
                "value": Decimal(str(value)),
                "unit": SENSOR_UNITS[sensor_type],
                "status": "normal",
            }
        )
    return items
