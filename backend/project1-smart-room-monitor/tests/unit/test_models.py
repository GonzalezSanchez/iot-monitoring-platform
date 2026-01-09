"""
Unit tests for models
"""
import pytest
from datetime import datetime
from src.models.sensor_event import SensorEvent
from src.models.room import Room, RoomState


class TestSensorEvent:
    """Test SensorEvent model"""

    def test_create_valid_event(self):
        """Test creating valid sensor event"""
        fixed_time = datetime(2026, 1, 9, 12, 0, 0)
        event = SensorEvent(
            room_id="room-a",
            sensor_type="temperature",
            value=22.5,
            timestamp=fixed_time,
        )

        assert event.room_id == "room-a"
        assert event.sensor_type == "temperature"
        assert event.value == 22.5
        assert event.unit == "°C"  # Auto-set
        assert event.status == "normal"  # Default

    def test_invalid_sensor_type(self):
        """Test that invalid sensor type raises error"""
        fixed_time = datetime(2026, 1, 9, 12, 0, 0)
        with pytest.raises(ValueError):
            SensorEvent(
                room_id="room-a",
                sensor_type="invalid",
                value=22.5,
                timestamp=fixed_time,
            )

    @pytest.mark.parametrize(
        "sensor_type,value,expected_unit",
        [
            ("temperature", 22.5, "°C"),
            ("humidity", 60.0, "%"),
            ("occupancy", 5, "people"),
            ("motion", 1, "boolean"),
        ],
    )
    def test_auto_unit_assignment(self, sensor_type, value, expected_unit):
        """Test automatic unit assignment based on sensor type"""
        fixed_time = datetime(2026, 1, 9, 12, 0, 0)
        event = SensorEvent(
            room_id="room-a",
            sensor_type=sensor_type,
            value=value,
            timestamp=fixed_time,
        )
        assert event.unit == expected_unit

    def test_to_dynamodb_item(self):
        """Test conversion to DynamoDB format"""
        fixed_time = datetime(2026, 1, 9, 12, 0, 0)
        event = SensorEvent(
            room_id="room-a",
            sensor_type="temperature",
            value=22.5,
            timestamp=fixed_time,
        )

        item = event.to_dynamodb_item()

        assert item["room_id"] == "room-a"
        assert item["sensor_type"] == "temperature"
        assert item["value"] == 22.5
        assert "timestamp" in item
        assert isinstance(item["timestamp"], str)
        assert item["timestamp"].startswith("2026-01-09T12:00:00")
        assert item["status"] == "normal"
        assert "event_id" in item

    def test_timestamp_parsing_from_string(self):
        """Test parsing timestamp from ISO string"""
        event = SensorEvent(
            room_id="room-a",
            sensor_type="temperature",
            value=22.5,
            timestamp="2026-01-09T12:00:00Z",
        )

        assert isinstance(event.timestamp, datetime)


class TestRoom:
    """Test Room model"""

    def test_create_room(self):
        """Test creating room"""
        fixed_time = datetime(2026, 1, 9, 12, 0, 0)
        room = Room(
            room_id="room-a",
            name="Conference Room A",
            last_update=fixed_time,
        )

        assert room.room_id == "room-a"
        assert room.name == "Conference Room A"
        assert room.status == "active"
        assert room.alert_count_24h == 0

    def test_room_state(self):
        """Test room state updates"""
        fixed_time = datetime(2026, 1, 9, 12, 0, 0)
        state = RoomState(temperature=22.5, motion=True, occupancy=5)

        room = Room(
            room_id="room-a",
            name="Room A",
            last_update=fixed_time,
            current_state=state,
        )

        assert room.current_state.temperature == 22.5
        assert room.current_state.motion is True
        assert room.current_state.occupancy == 5

    def test_room_state_motion_false(self):
        """Test room state with motion=False"""
        fixed_time = datetime(2026, 1, 9, 12, 0, 0)
        state = RoomState(temperature=20.0, motion=False, occupancy=0)

        room = Room(
            room_id="room-b",
            name="Room B",
            last_update=fixed_time,
            current_state=state,
        )

        assert room.current_state.motion is False
        assert room.current_state.occupancy == 0

    def test_to_dynamodb_item(self):
        """Test Room to DynamoDB conversion"""
        fixed_time = datetime(2026, 1, 9, 12, 0, 0)
        room = Room(
            room_id="room-a",
            name="Conference Room A",
            status="warning",
            last_update=fixed_time,
            current_state=RoomState(temperature=28.0, occupancy=10),
            alert_count_24h=2,
        )

        item = room.to_dynamodb_item()

        assert item["room_id"] == "room-a"
        assert item["name"] == "Conference Room A"
        assert item["status"] == "warning"
        assert item["alert_count_24h"] == 2
        assert "current_state" in item
        assert item["current_state"]["temperature"] == 28.0
        assert "last_update" in item
        assert isinstance(item["last_update"], str)
        assert item["last_update"].startswith("2026-01-09T12:00:00")

    def test_from_dynamodb_item(self):
        """Test creating Room from DynamoDB item"""
        item = {
            "room_id": "room-a",
            "name": "Conference Room A",
            "status": "active",
            "last_update": "2026-01-09T12:00:00",
            "current_state": {"temperature": 22.5, "occupancy": 5},
            "alert_count_24h": 0,
        }

        room = Room.from_dynamodb_item(item)

        assert room.room_id == "room-a"
        assert room.name == "Conference Room A"
        assert room.current_state.temperature == 22.5
        assert room.current_state.occupancy == 5
        assert isinstance(room.last_update, datetime)
        assert room.last_update == datetime(2026, 1, 9, 12, 0, 0)
