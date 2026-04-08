"""
Unit tests for EventService
"""
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from services.event_service import EventService, EventServiceError
from src.models.room import Room, RoomState


@pytest.fixture
def mock_event_repo():
    repo = MagicMock()
    repo.save_event.return_value = {}
    return repo


@pytest.fixture
def mock_room_repo():
    repo = MagicMock()
    repo.get_room.return_value = None
    repo.save_room.return_value = None
    return repo


@pytest.fixture
def event_service(mock_event_repo, mock_room_repo):
    return EventService(
        event_repo=mock_event_repo,
        room_repo=mock_room_repo,
    )


@pytest.fixture
def valid_event_data():
    return {
        "room_id": "room-1",
        "sensor_type": "temperature",
        "value": 22.5,
        "timestamp": "2026-01-09T12:00:00",
    }


class TestEventServiceProcessEvent:
    """Tests for EventService.process_event"""

    def test_process_valid_event_returns_success(self, event_service, valid_event_data):
        result = event_service.process_event(valid_event_data)
        assert result["processing_status"] == "success"
        assert "event_id" in result
        assert "event_status" in result

    def test_process_event_saves_to_repository(
        self, event_service, mock_event_repo, valid_event_data
    ):
        event_service.process_event(valid_event_data)
        mock_event_repo.save_event.assert_called_once()

    def test_process_event_updates_room(
        self, event_service, mock_room_repo, valid_event_data
    ):
        event_service.process_event(valid_event_data)
        mock_room_repo.save_room.assert_called_once()

    def test_process_event_creates_new_room_if_not_exists(
        self, event_service, mock_room_repo, valid_event_data
    ):
        mock_room_repo.get_room.return_value = None
        event_service.process_event(valid_event_data)
        saved_room = mock_room_repo.save_room.call_args[0][0]
        assert saved_room.room_id == "room-1"

    def test_process_event_updates_existing_room(
        self, event_service, mock_room_repo, valid_event_data
    ):
        existing_room = Room(
            room_id="room-1",
            name="Room 1",
            last_update=datetime(2026, 1, 9, 11, 0, 0),
            current_state=RoomState(temperature=20.0),
        )
        mock_room_repo.get_room.return_value = existing_room
        event_service.process_event(valid_event_data)
        saved_room = mock_room_repo.save_room.call_args[0][0]
        assert saved_room.current_state.temperature == 22.5

    def test_process_invalid_sensor_type_raises_error(self, event_service):
        with pytest.raises(EventServiceError):
            event_service.process_event(
                {
                    "room_id": "room-1",
                    "sensor_type": "invalid_type",
                    "value": 22.5,
                    "timestamp": "2026-01-09T12:00:00",
                }
            )

    def test_process_warning_event_increments_alert_count(
        self, event_service, mock_room_repo
    ):
        existing_room = Room(
            room_id="room-1",
            name="Room 1",
            last_update=datetime(2026, 1, 9, 11, 0, 0),
            alert_count_24h=0,
        )
        mock_room_repo.get_room.return_value = existing_room
        event_service.process_event(
            {
                "room_id": "room-1",
                "sensor_type": "temperature",
                "value": 32.0,  # Alert threshold
                "timestamp": "2026-01-09T12:00:00",
            }
        )
        saved_room = mock_room_repo.save_room.call_args[0][0]
        assert saved_room.alert_count_24h == 1

    def test_process_humidity_event_updates_room_state(
        self, event_service, mock_room_repo
    ):
        mock_room_repo.get_room.return_value = None
        event_service.process_event(
            {
                "room_id": "room-1",
                "sensor_type": "humidity",
                "value": 65.0,
                "timestamp": "2026-01-09T12:00:00",
            }
        )
        saved_room = mock_room_repo.save_room.call_args[0][0]
        assert saved_room.current_state.humidity == 65.0

    def test_process_occupancy_event_updates_room_state(
        self, event_service, mock_room_repo
    ):
        mock_room_repo.get_room.return_value = None
        event_service.process_event(
            {
                "room_id": "room-1",
                "sensor_type": "occupancy",
                "value": 8,
                "timestamp": "2026-01-09T12:00:00",
            }
        )
        saved_room = mock_room_repo.save_room.call_args[0][0]
        assert saved_room.current_state.occupancy == 8

    def test_process_motion_event_updates_room_state(
        self, event_service, mock_room_repo
    ):
        mock_room_repo.get_room.return_value = None
        event_service.process_event(
            {
                "room_id": "room-1",
                "sensor_type": "motion",
                "value": 1,
                "timestamp": "2026-01-09T12:00:00",
            }
        )
        saved_room = mock_room_repo.save_room.call_args[0][0]
        assert saved_room.current_state.motion is True

    def test_room_update_failure_does_not_fail_event(
        self, event_service, mock_room_repo, valid_event_data
    ):
        mock_room_repo.get_room.side_effect = Exception("DB error")
        # Should not raise — room update failure is non-critical
        result = event_service.process_event(valid_event_data)
        assert result["processing_status"] == "success"
