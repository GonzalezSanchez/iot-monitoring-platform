"""Unit tests for sensor event schema validation and WAP batch splitting.

Tests import from scripts/validate.py — the same validation logic
the PySpark Silver job will apply in Fase 3 (replicated in StructType + filter).
Pure Python — no PySpark, no Azure, no dbt required.
"""

from scripts.validate import VALID_SENSOR_TYPES, split_wap, validate_sensor_event

VALID_EVENT: dict[str, object] = {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "room_id": "room_001",
    "sensor_type": "temperature",
    "value": 21.5,
    "timestamp": "2024-01-01T00:00:00+00:00",
}


class TestSensorEventValidation:
    def test_valid_event_passes(self) -> None:
        is_valid, reason = validate_sensor_event(VALID_EVENT)
        assert is_valid, reason

    def test_missing_field_fails(self) -> None:
        event = {k: v for k, v in VALID_EVENT.items() if k != "timestamp"}
        is_valid, reason = validate_sensor_event(event)
        assert not is_valid
        assert "timestamp" in reason

    def test_invalid_sensor_type_fails(self) -> None:
        event = {**VALID_EVENT, "sensor_type": "radiation"}
        is_valid, reason = validate_sensor_event(event)
        assert not is_valid
        assert "sensor_type" in reason

    def test_non_numeric_value_fails(self) -> None:
        event = {**VALID_EVENT, "value": "high"}
        is_valid, reason = validate_sensor_event(event)
        assert not is_valid
        assert "numeric" in reason

    def test_empty_room_id_fails(self) -> None:
        event = {**VALID_EVENT, "room_id": ""}
        is_valid, reason = validate_sensor_event(event)
        assert not is_valid

    def test_integer_value_is_valid(self) -> None:
        event = {**VALID_EVENT, "sensor_type": "occupancy", "value": 5}
        is_valid, _ = validate_sensor_event(event)
        assert is_valid

    def test_all_sensor_types_are_valid(self) -> None:
        for sensor_type in VALID_SENSOR_TYPES:
            event = {**VALID_EVENT, "sensor_type": sensor_type}
            is_valid, reason = validate_sensor_event(event)
            assert is_valid, f"{sensor_type}: {reason}"


class TestWAPBatch:
    """Verifies the Write-Audit-Publish split: good records → Silver, bad → quarantine."""

    def test_wap_splits_good_and_bad_records(self) -> None:
        events: list[dict[str, object]] = [
            {**VALID_EVENT, "room_id": "room_001", "value": 20.0},
            {**VALID_EVENT, "room_id": "room_002", "value": 450.0, "sensor_type": "co2"},
            {**VALID_EVENT, "room_id": ""},  # bad — empty room_id
            {**VALID_EVENT, "sensor_type": "unknown"},  # bad — invalid type
        ]
        good, quarantine = split_wap(events)
        assert len(good) == 2
        assert len(quarantine) == 2

    def test_pipeline_continues_when_all_records_quarantined(self) -> None:
        """Pipeline must not crash when every record fails validation."""
        bad_events: list[dict[str, object]] = [{**VALID_EVENT, "room_id": ""}]
        good, _ = split_wap(bad_events)
        assert good == []

    def test_quarantine_records_preserve_all_fields(self) -> None:
        """Bad records go to quarantine with all original fields intact for manual review."""
        events: list[dict[str, object]] = [
            {**VALID_EVENT, "sensor_type": "radiation"},
            {**VALID_EVENT, "value": "NaN"},
        ]
        _, quarantine = split_wap(events)
        assert len(quarantine) == 2
        for record in quarantine:
            assert "event_id" in record
            assert "timestamp" in record
