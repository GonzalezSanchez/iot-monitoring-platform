"""
Unit tests for repositories (RoomRepository and EventRepository)
Using moto to mock DynamoDB
"""
from datetime import datetime
from decimal import Decimal

import boto3
import pytest
from moto import mock_dynamodb
from repositories.event_repository import EventRepository
from repositories.room_repository import RoomRepository
from src.models.room import Room, RoomState

TABLE_ROOMS = "RoomStatus"
TABLE_EVENTS = "SensorEvents"
REGION = "eu-west-1"


@pytest.fixture
def dynamodb():
    """Mocked DynamoDB resource with both tables created"""
    with mock_dynamodb():
        resource = boto3.resource("dynamodb", region_name=REGION)

        resource.create_table(
            TableName=TABLE_ROOMS,
            KeySchema=[{"AttributeName": "room_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "room_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        resource.create_table(
            TableName=TABLE_EVENTS,
            KeySchema=[
                {"AttributeName": "room_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "room_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield resource


@pytest.fixture
def room_repo(dynamodb):
    return RoomRepository(dynamodb_resource=dynamodb, table_name=TABLE_ROOMS)


@pytest.fixture
def event_repo(dynamodb):
    return EventRepository(dynamodb_resource=dynamodb, table_name=TABLE_EVENTS)


@pytest.fixture
def sample_room():
    return Room(
        room_id="room-1",
        name="Conference Room 1",
        status="active",
        last_update=datetime(2026, 1, 9, 12, 0, 0),
        current_state=RoomState(temperature=22.5, occupancy=5),
        alert_count_24h=0,
    )


@pytest.fixture
def sample_event_item():
    return {
        "room_id": "room-1",
        "timestamp": "2026-01-09T12:00:00",
        "event_id": "evt-001",
        "sensor_type": "temperature",
        "value": Decimal("22.5"),
        "status": "normal",
        "unit": "°C",
    }


class TestRoomRepository:
    """Tests for RoomRepository"""

    def test_save_and_get_room(self, room_repo, sample_room):
        room_repo.save_room(sample_room)
        result = room_repo.get_room("room-1")
        assert result is not None
        assert result.room_id == "room-1"
        assert result.name == "Conference Room 1"

    def test_get_room_not_found(self, room_repo):
        result = room_repo.get_room("nonexistent")
        assert result is None

    def test_get_all_rooms_empty(self, room_repo):
        rooms = room_repo.get_all_rooms()
        assert rooms == []

    def test_get_all_rooms_with_data(self, room_repo, sample_room):
        room_repo.save_room(sample_room)
        room2 = Room(
            room_id="room-2",
            name="Room 2",
            last_update=datetime(2026, 1, 9, 12, 0, 0),
        )
        room_repo.save_room(room2)
        rooms = room_repo.get_all_rooms()
        assert len(rooms) == 2

    def test_save_room_updates_existing(self, room_repo, sample_room):
        room_repo.save_room(sample_room)
        sample_room.status = "warning"
        sample_room.alert_count_24h = 1
        room_repo.save_room(sample_room)
        result = room_repo.get_room("room-1")
        assert result.status == "warning"
        assert result.alert_count_24h == 1

    def test_room_state_temperature_preserved(self, room_repo, sample_room):
        room_repo.save_room(sample_room)
        result = room_repo.get_room("room-1")
        assert result.current_state.temperature == 22.5
        assert result.current_state.occupancy == 5


class TestEventRepository:
    """Tests for EventRepository"""

    def test_save_and_get_event(self, event_repo, sample_event_item):
        event_repo.save_event(sample_event_item)
        events = event_repo.get_events_by_room("room-1")
        assert len(events) == 1
        assert events[0]["event_id"] == "evt-001"

    def test_get_events_empty_room(self, event_repo):
        events = event_repo.get_events_by_room("nonexistent")
        assert events == []

    def test_save_multiple_events(self, event_repo):
        for i in range(3):
            event_repo.save_event(
                {
                    "room_id": "room-1",
                    "timestamp": f"2026-01-09T12:0{i}:00",
                    "event_id": f"evt-00{i}",
                    "sensor_type": "temperature",
                    "value": Decimal(str(22.0 + i)),
                    "status": "normal",
                    "unit": "°C",
                }
            )
        events = event_repo.get_events_by_room("room-1", limit=10)
        assert len(events) == 3

    def test_get_events_limit(self, event_repo):
        for i in range(5):
            event_repo.save_event(
                {
                    "room_id": "room-1",
                    "timestamp": f"2026-01-09T12:0{i}:00",
                    "event_id": f"evt-00{i}",
                    "sensor_type": "temperature",
                    "value": Decimal("22.0"),
                    "status": "normal",
                    "unit": "°C",
                }
            )
        events = event_repo.get_events_by_room("room-1", limit=2)
        assert len(events) <= 2

    def test_get_events_with_start_time(self, event_repo):
        event_repo.save_event(
            {
                "room_id": "room-1",
                "timestamp": "2026-01-09T10:00:00",
                "event_id": "evt-old",
                "sensor_type": "temperature",
                "value": Decimal("22.0"),
                "status": "normal",
                "unit": "°C",
            }
        )
        event_repo.save_event(
            {
                "room_id": "room-1",
                "timestamp": "2026-01-09T15:00:00",
                "event_id": "evt-new",
                "sensor_type": "temperature",
                "value": Decimal("25.0"),
                "status": "normal",
                "unit": "°C",
            }
        )
        start = datetime(2026, 1, 9, 12, 0, 0)
        events = event_repo.get_events_by_room("room-1", start_time=start)
        assert all(e["timestamp"] >= "2026-01-09T12:00:00" for e in events)
