"""Sensor event validation — logic shared between ingestion scripts and PySpark jobs.

In Fase 3 this validation logic is replicated in PySpark (StructType + DataFrame filter).
This module enables unit testing the WAP rules without a Spark context.
"""

REQUIRED_FIELDS = frozenset({"event_id", "room_id", "sensor_type", "value", "timestamp"})
VALID_SENSOR_TYPES = frozenset({"temperature", "co2", "occupancy", "humidity"})


def validate_sensor_event(event: dict[str, object]) -> tuple[bool, str]:
    """Validate a sensor event record. Returns (is_valid, reason)."""
    missing = REQUIRED_FIELDS - event.keys()
    if missing:
        return False, f"missing fields: {sorted(missing)}"

    if event["sensor_type"] not in VALID_SENSOR_TYPES:
        return False, f"unknown sensor_type: {event['sensor_type']}"

    if not isinstance(event["value"], int | float):
        return False, f"value must be numeric, got: {type(event['value']).__name__}"

    if not isinstance(event["room_id"], str) or not event["room_id"]:
        return False, "room_id must be a non-empty string"

    return True, ""


def split_wap(
    events: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Split a batch into (good, quarantine) using the Write-Audit-Publish pattern."""
    good = []
    quarantine = []
    for event in events:
        if validate_sensor_event(event)[0]:
            good.append(event)
        else:
            quarantine.append(event)
    return good, quarantine
