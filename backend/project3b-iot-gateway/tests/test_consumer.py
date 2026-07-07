"""Consumer tests — the 3b-2 test contract from docs/project3-prd.md §7:

1. valid message → exactly the shared-contract item shape (golden test)
2. malformed payload → DLQ with original + error, nothing written
3. duplicate delivery → single item (idempotency)
4. unknown room/device mapping → DLQ, not dropped
"""

import json
from decimal import Decimal

import pytest

from consumer import config as consumer_config
from consumer import normalizer
from consumer.main import handle_message
from tests.conftest import FakeDlq


def gateway_message(**overrides):
    """A message exactly as the gateway produces it (see gateway/main.py)."""
    message = {
        "schema_version": 1,
        "message_id": "5f7b6cbe-4f5c-4e6a-9c58-2f6d7a8b9c0d",
        "device_id": "sensor-001",
        "device_type": "temperature_sensor",
        "location": "room-101",
        "payload": {"temperature": 21.5, "humidity": 48},
        "timestamp": "2026-07-06T20:00:00+00:00",
        "received_at": "2026-07-06T20:00:01Z",
    }
    message.update(overrides)
    return message


# ---------------------------------------------------------------------------
# 1. Golden test — the exact item shape project 1b writes
#    (SensorEvent.to_dynamodb_item() in project1b .../models/sensor_event.py)
# ---------------------------------------------------------------------------


def test_normalize_matches_1b_contract_shape():
    items = normalizer.normalize(gateway_message(payload={"temperature": 21.5}))
    assert len(items) == 1
    item = items[0]
    assert item == {
        "room_id": "room-101",
        "timestamp": "2026-07-06T20:00:00+00:00",
        "event_id": item["event_id"],  # deterministic uuid5, asserted below
        "sensor_type": "temperature",
        "value": Decimal("21.5"),
        "unit": "°C",
        "status": "normal",
    }
    # exact key set and types of the 1b contract
    assert set(item) == {"room_id", "timestamp", "event_id", "sensor_type", "value", "unit", "status"}
    assert isinstance(item["value"], Decimal)


def test_normalize_fans_out_per_sensor_with_unique_keys():
    items = normalizer.normalize(gateway_message())
    assert [i["sensor_type"] for i in items] == ["humidity", "temperature"]
    # same room, distinct sort keys (deterministic microsecond offsets)
    assert len({i["timestamp"] for i in items}) == 2


def test_normalize_is_deterministic_for_idempotency():
    assert normalizer.normalize(gateway_message()) == normalizer.normalize(gateway_message())


async def test_valid_message_written_to_both_tables(contract_tables):
    events, rooms = contract_tables
    dlq = FakeDlq()

    outcome = await handle_message(json.dumps(gateway_message()).encode(), dlq)

    assert outcome == "written"
    assert dlq.records == []
    written = events.scan()["Items"]
    assert len(written) == 2
    room = rooms.get_item(Key={"room_id": "room-101"})["Item"]
    assert room["current_state"] == {"temperature": Decimal("21.5"), "humidity": Decimal("48")}
    assert room["status"] == "active"
    assert room["last_update"] == max(i["timestamp"] for i in written)


# ---------------------------------------------------------------------------
# 2. Malformed → DLQ, nothing written
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        b"not json at all",
        json.dumps(gateway_message(timestamp="yesterday")).encode(),
        json.dumps(gateway_message(payload={"temperature": "warm"})).encode(),
        json.dumps(gateway_message(payload={"pressure": 1013})).encode(),  # no known sensors
    ],
)
async def test_malformed_message_goes_to_dlq_and_writes_nothing(contract_tables, raw):
    events, rooms = contract_tables
    dlq = FakeDlq()

    outcome = await handle_message(raw, dlq)

    assert outcome == "dlq"
    assert len(dlq.records) == 1
    record = json.loads(dlq.records[0])
    assert record["error"]
    assert record["original"] == raw.decode(errors="replace")  # original preserved
    assert events.scan()["Count"] == 0
    assert rooms.scan()["Count"] == 0


# ---------------------------------------------------------------------------
# 3. Duplicate delivery → single item set (idempotency)
# ---------------------------------------------------------------------------


async def test_duplicate_delivery_writes_single_item_set(contract_tables):
    events, _ = contract_tables
    raw = json.dumps(gateway_message()).encode()
    dlq = FakeDlq()

    assert await handle_message(raw, dlq) == "written"
    assert await handle_message(raw, dlq) == "written"

    written = events.scan()["Items"]
    assert len(written) == 2  # not 4 — same keys overwrite
    assert len({i["event_id"] for i in written}) == 2


# ---------------------------------------------------------------------------
# 4. Unknown room mapping → DLQ, not dropped
# ---------------------------------------------------------------------------


async def test_unknown_room_mapping_goes_to_dlq(contract_tables):
    events, _ = contract_tables
    dlq = FakeDlq()
    raw = json.dumps(gateway_message(location=None)).encode()

    outcome = await handle_message(raw, dlq)

    assert outcome == "dlq"
    record = json.loads(dlq.records[0])
    assert "unknown room mapping" in record["error"]
    assert "sensor-001" in record["error"]
    assert events.scan()["Count"] == 0


def test_dlq_record_carries_consumer_group():
    from consumer.main import _dlq_record

    record = json.loads(_dlq_record(b"broken", "some reason"))
    assert record["consumer_group"] == consumer_config.CONSUMER_GROUP
    assert record["failed_at"]
