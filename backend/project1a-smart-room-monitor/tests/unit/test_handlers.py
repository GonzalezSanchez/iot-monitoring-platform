"""
Unit tests for Lambda handlers
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.room import Room, RoomState


@pytest.fixture
def mock_room():
    return Room(
        room_id="room-1",
        name="Conference Room 1",
        status="active",
        last_update=datetime(2026, 1, 9, 12, 0, 0),
        current_state=RoomState(temperature=22.5, occupancy=5),
        alert_count_24h=0,
    )


@pytest.fixture
def lambda_context():
    return MagicMock()


class TestIngestEventHandler:
    """Tests for ingest_event Lambda handler"""

    def test_success(self, lambda_context):
        mock_service = MagicMock()
        mock_service.process_event.return_value = {
            "event_id": "evt-001",
            "event_status": "normal",
            "processing_status": "success",
            "timestamp": "2026-01-09T12:00:00",
        }
        with patch("handlers.ingest_event.event_service", mock_service):
            from handlers.ingest_event import lambda_handler

            event = {
                "body": json.dumps(
                    {
                        "room_id": "room-1",
                        "sensor_type": "temperature",
                        "value": 22.5,
                        "timestamp": "2026-01-09T12:00:00",
                    }
                )
            }
            response = lambda_handler(event, lambda_context)
            assert response["statusCode"] == 201
            body = json.loads(response["body"])
            assert body["processing_status"] == "success"

    def test_empty_body_returns_400(self, lambda_context):
        with patch("handlers.ingest_event.event_service", MagicMock()):
            from handlers.ingest_event import lambda_handler

            response = lambda_handler({"body": None}, lambda_context)
            assert response["statusCode"] == 400

    def test_invalid_json_returns_400(self, lambda_context):
        with patch("handlers.ingest_event.event_service", MagicMock()):
            from handlers.ingest_event import lambda_handler

            response = lambda_handler({"body": "not-json"}, lambda_context)
            assert response["statusCode"] == 400

    def test_missing_fields_returns_400(self, lambda_context):
        from services.event_service import EventServiceError

        with patch("handlers.ingest_event.event_service") as mock_service:
            mock_service.process_event.side_effect = EventServiceError("Validation error")
            from handlers.ingest_event import lambda_handler

            response = lambda_handler({"body": json.dumps({"room_id": "room-1"})}, lambda_context)
            assert response["statusCode"] == 422

    def test_event_service_error_returns_422(self, lambda_context):
        from services.event_service import EventServiceError

        mock_service = MagicMock()
        mock_service.process_event.side_effect = EventServiceError("Validation failed")
        with patch("handlers.ingest_event.event_service", mock_service):
            from handlers.ingest_event import lambda_handler

            event = {
                "body": json.dumps(
                    {
                        "room_id": "room-1",
                        "sensor_type": "temperature",
                        "value": 22.5,
                        "timestamp": "2026-01-09T12:00:00",
                    }
                )
            }
            response = lambda_handler(event, lambda_context)
            assert response["statusCode"] == 422

    def test_unexpected_error_returns_500(self, lambda_context):
        mock_service = MagicMock()
        mock_service.process_event.side_effect = RuntimeError("unexpected")
        with patch("handlers.ingest_event.event_service", mock_service):
            from handlers.ingest_event import lambda_handler

            event = {
                "body": json.dumps(
                    {
                        "room_id": "room-1",
                        "sensor_type": "temperature",
                        "value": 22.5,
                        "timestamp": "2026-01-09T12:00:00",
                    }
                )
            }
            response = lambda_handler(event, lambda_context)
            assert response["statusCode"] == 500

    def test_body_as_dict_not_string(self, lambda_context):
        """Body can be a dict (API Gateway v2 passes parsed body)"""
        mock_service = MagicMock()
        mock_service.process_event.return_value = {
            "event_id": "evt-001",
            "event_status": "normal",
            "processing_status": "success",
            "timestamp": "2026-01-09T12:00:00",
        }
        with patch("handlers.ingest_event.event_service", mock_service):
            from handlers.ingest_event import lambda_handler

            event = {
                "body": {
                    "room_id": "room-1",
                    "sensor_type": "temperature",
                    "value": 22.5,
                    "timestamp": "2026-01-09T12:00:00",
                }
            }
            response = lambda_handler(event, lambda_context)
            assert response["statusCode"] == 201


class TestGetRoomsHandler:
    """Tests for get_rooms Lambda handler"""

    def test_returns_rooms(self, lambda_context, mock_room):
        mock_repo = MagicMock()
        mock_repo.get_all_rooms.return_value = [mock_room]
        with patch("handlers.get_rooms.room_repository", mock_repo):
            from handlers.get_rooms import lambda_handler

            response = lambda_handler({}, lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["count"] == 1
            assert len(body["rooms"]) == 1

    def test_returns_empty_list(self, lambda_context):
        mock_repo = MagicMock()
        mock_repo.get_all_rooms.return_value = []
        with patch("handlers.get_rooms.room_repository", mock_repo):
            from handlers.get_rooms import lambda_handler

            response = lambda_handler({}, lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["count"] == 0

    def test_repository_error_returns_500(self, lambda_context):
        mock_repo = MagicMock()
        mock_repo.get_all_rooms.side_effect = Exception("DB error")
        with patch("handlers.get_rooms.room_repository", mock_repo):
            from handlers.get_rooms import lambda_handler

            response = lambda_handler({}, lambda_context)
            assert response["statusCode"] == 500


class TestGetRoomDetailHandler:
    """Tests for get_room_detail Lambda handler"""

    def test_returns_room_with_events(self, lambda_context, mock_room):
        mock_room_repo = MagicMock()
        mock_room_repo.get_room.return_value = mock_room
        mock_event_repo = MagicMock()
        mock_event_repo.get_events_by_room.return_value = [{"event_id": "evt-001"}]
        with (
            patch("handlers.get_room_detail.room_repository", mock_room_repo),
            patch("handlers.get_room_detail.event_repository", mock_event_repo),
        ):
            from handlers.get_room_detail import lambda_handler

            event = {"pathParameters": {"id": "room-1"}}
            response = lambda_handler(event, lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["event_count"] == 1
            assert body["room"]["room_id"] == "room-1"

    def test_missing_room_id_returns_400(self, lambda_context):
        with (
            patch("handlers.get_room_detail.room_repository", MagicMock()),
            patch("handlers.get_room_detail.event_repository", MagicMock()),
        ):
            from handlers.get_room_detail import lambda_handler

            response = lambda_handler({"pathParameters": {}}, lambda_context)
            assert response["statusCode"] == 400

    def test_room_not_found_returns_404(self, lambda_context):
        mock_room_repo = MagicMock()
        mock_room_repo.get_room.return_value = None
        with (
            patch("handlers.get_room_detail.room_repository", mock_room_repo),
            patch("handlers.get_room_detail.event_repository", MagicMock()),
        ):
            from handlers.get_room_detail import lambda_handler

            event = {"pathParameters": {"id": "nonexistent"}}
            response = lambda_handler(event, lambda_context)
            assert response["statusCode"] == 404

    def test_no_path_parameters_returns_400(self, lambda_context):
        with (
            patch("handlers.get_room_detail.room_repository", MagicMock()),
            patch("handlers.get_room_detail.event_repository", MagicMock()),
        ):
            from handlers.get_room_detail import lambda_handler

            response = lambda_handler({}, lambda_context)
            assert response["statusCode"] == 400

    def test_repository_error_returns_500(self, lambda_context):
        mock_room_repo = MagicMock()
        mock_room_repo.get_room.side_effect = Exception("DB error")
        with (
            patch("handlers.get_room_detail.room_repository", mock_room_repo),
            patch("handlers.get_room_detail.event_repository", MagicMock()),
        ):
            from handlers.get_room_detail import lambda_handler

            event = {"pathParameters": {"id": "room-1"}}
            response = lambda_handler(event, lambda_context)
            assert response["statusCode"] == 500

    def test_room_id_from_room_id_param(self, lambda_context, mock_room):
        """Supports both 'id' and 'room_id' path params"""
        mock_room_repo = MagicMock()
        mock_room_repo.get_room.return_value = mock_room
        mock_event_repo = MagicMock()
        mock_event_repo.get_events_by_room.return_value = []
        with (
            patch("handlers.get_room_detail.room_repository", mock_room_repo),
            patch("handlers.get_room_detail.event_repository", mock_event_repo),
        ):
            from handlers.get_room_detail import lambda_handler

            event = {"pathParameters": {"room_id": "room-1"}}
            response = lambda_handler(event, lambda_context)
            assert response["statusCode"] == 200
