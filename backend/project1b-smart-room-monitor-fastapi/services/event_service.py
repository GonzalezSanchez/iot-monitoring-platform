"""
Event Service
Business logic for processing sensor events.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from models.room import Room, RoomState
from models.sensor_event import SensorEvent
from repositories.event_repository import EventRepository
from repositories.room_repository import RoomRepository
from services.anomaly_detector import AnomalyDetector

logger = logging.getLogger(__name__)


class EventServiceError(Exception):
    """Custom exception for EventService errors"""

    pass


class EventService:
    """Service for handling sensor events"""

    def __init__(
        self,
        event_repo: Optional[EventRepository] = None,
        room_repo: Optional[RoomRepository] = None,
        anomaly_detector: Optional[AnomalyDetector] = None,
    ):
        """
        Initialize EventService with dependency injection

        Args:
            event_repo: EventRepository instance (creates default if None)
            room_repo: RoomRepository instance (creates default if None)
            anomaly_detector: AnomalyDetector instance (creates default if None)
        """
        self.event_repo = event_repo or EventRepository()
        self.room_repo = room_repo or RoomRepository()
        self.anomaly_detector = anomaly_detector or AnomalyDetector()

    def process_event(self, event: SensorEvent) -> Dict[str, Any]:
        """
        Process an incoming sensor event end-to-end:
          1. Apply anomaly detection (sets event.status)
          2. Save event to DynamoDB
          3. Update room state (creates room if it doesn't exist yet)

        Args:
            event: Validated SensorEvent instance

        Returns:
            Dict with event_id, event_status, processing_status, timestamp

        Raises:
            EventServiceError: When a critical step fails
        """
        try:
            # 1. Anomaly detection — updates event.status in place
            event = self.anomaly_detector.apply_anomaly_detection(event)
            logger.info(
                "Anomaly detection done for %s / %s — status: %s",
                event.room_id,
                event.sensor_type,
                event.status,
            )

            # 2. Persist event
            self.event_repo.save_event(event.to_dynamodb_item())
            logger.info("Event saved: %s", event.event_id)

            # 3. Update room state (non-critical — log but don't fail)
            try:
                self._update_room_state(event)
            except Exception as exc:
                logger.warning(
                    "Room state update failed for %s (continuing): %s",
                    event.room_id,
                    exc,
                )

            return {
                "event_id": event.event_id,
                "event_status": event.status,
                "processing_status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            logger.error("Failed to process event: %s", exc, exc_info=True)
            raise EventServiceError(str(exc)) from exc

    def _update_room_state(self, event: SensorEvent) -> None:
        """
        Fetch (or create) the room and update its sensor state.
        """
        item = self.room_repo.get_room(event.room_id)

        if item:
            room = Room.from_dynamodb_item(item)
        else:
            logger.info("Creating new room record for: %s", event.room_id)
            room = Room(
                room_id=event.room_id,
                name=f"Room {event.room_id}",
                status="active",
                last_update=event.timestamp,
                current_state=RoomState(),
                alert_count_24h=0,
            )

        if event.sensor_type == "temperature":
            room.current_state.temperature = event.value
        elif event.sensor_type == "motion":
            room.current_state.motion = bool(event.value)
        elif event.sensor_type == "occupancy":
            room.current_state.occupancy = int(event.value)
        elif event.sensor_type == "humidity":
            room.current_state.humidity = event.value

        room.last_update = event.timestamp

        if event.status in ("warning", "alert"):
            room.status = event.status
            room.alert_count_24h += 1

        self.room_repo.save_room(room)
        logger.debug("Room state updated: %s", room.room_id)
