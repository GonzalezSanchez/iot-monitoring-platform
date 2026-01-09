"""
Event Service
Business logic for processing sensor events with error handling
"""
import logging
from datetime import datetime
from typing import Dict, Optional
from ulid import ULID
from botocore.exceptions import ClientError
from pydantic import ValidationError

from src.models.sensor_event import SensorEvent
from src.models.room import Room, RoomState
from src.repositories.event_repository import EventRepository
from src.repositories.room_repository import RoomRepository
from src.services.anomaly_detector import AnomalyDetector

# Configure logger
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

    def process_event(self, event_data: dict) -> Dict:
        """
        Process incoming sensor event with error handling

        Args:
            event_data: Dictionary with sensor event data

        Returns:
            Dict with:
                - event_id: Unique event identifier
                - event_status: Anomaly status (normal/warning/alert)
                - processing_status: Processing result (success)
                - timestamp: Processing completion time

        Raises:
            EventServiceError: When processing fails
        """
        try:
            # Validate and create event model
            event = self._validate_event(event_data)
            if not event:
                raise EventServiceError("Event validation failed")

            # Generate event_id if not provided (using ULID for uniqueness)
            if not event.event_id:
                event.event_id = str(ULID())
                logger.debug(f"Generated ULID event_id: {event.event_id}")

            # Apply anomaly detection before saving
            event = self.anomaly_detector.apply_anomaly_detection(event)
            logger.debug(f"Anomaly detection applied, status: {event.status}")

            # Save event with error handling
            if not self._save_event(event):
                raise EventServiceError("Failed to save event to database")

            # Update room state with error handling (non-critical)
            if not self._update_room_state(event):
                logger.warning(
                    f"Failed to update room state for {event.room_id}, continuing anyway"
                )
                # Don't fail entire process if room update fails

            logger.info(
                f"Successfully processed event {event.event_id} for room {event.room_id}"
            )

            return {
                "event_id": event.event_id,
                "event_status": event.status,
                "processing_status": "success",
                "timestamp": datetime.now().isoformat(),
            }

        except ValidationError as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(error_msg)
            raise EventServiceError(error_msg)
        except ClientError as e:
            error_msg = f"DynamoDB error: {e.response['Error']['Message']}"
            logger.error(error_msg)
            raise EventServiceError(error_msg)
        except EventServiceError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            error_msg = f"Unexpected error processing event: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise EventServiceError(error_msg)

    def _validate_event(self, event_data: dict) -> Optional[SensorEvent]:
        """
        Validate event data and return SensorEvent

        Args:
            event_data: Raw event data dictionary

        Returns:
            SensorEvent object or None if validation fails
        """
        try:
            event = SensorEvent(**event_data)
            logger.debug(f"Event validated: {event.room_id} - {event.sensor_type}")
            return event
        except ValidationError as e:
            logger.error(f"Event validation failed: {e}")
            raise

    def _save_event(self, event: SensorEvent) -> bool:
        """
        Save event to repository with error handling

        Args:
            event: SensorEvent to save

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            self.event_repo.save_event(event.to_dynamodb_item())
            logger.debug(f"Event saved: {event.event_id}")
            return True
        except ClientError as e:
            logger.error(f"Failed to save event {event.event_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving event: {e}")
            return False

    def _update_room_state(self, event: SensorEvent) -> bool:
        """
        Update room status based on new event

        Args:
            event: SensorEvent containing room update data

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            room = self.room_repo.get_room(event.room_id)

            if not room:
                # Create new room if doesn't exist
                logger.info(f"Creating new room: {event.room_id}")
                room = Room(
                    room_id=event.room_id,
                    name=f"Room {event.room_id}",
                    status="active",
                    last_update=event.timestamp,
                    current_state=RoomState(),
                    alert_count_24h=0,
                )

            # Update room state based on sensor type
            if event.sensor_type == "temperature":
                room.current_state.temperature = event.value
            elif event.sensor_type == "motion":
                room.current_state.motion = bool(event.value)
            elif event.sensor_type == "occupancy":
                room.current_state.occupancy = int(event.value)
            elif event.sensor_type == "humidity":
                room.current_state.humidity = event.value

            room.last_update = event.timestamp

            # Update status if there's an alert
            if event.status in ["warning", "alert"]:
                room.status = event.status
                room.alert_count_24h += 1
                logger.warning(
                    f"Alert detected for room {room.room_id}: {event.status}"
                )

            self.room_repo.save_room(room)
            logger.debug(f"Room state updated: {room.room_id}")
            return True

        except ClientError as e:
            logger.error(f"DynamoDB error updating room state: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating room {event.room_id}: {e}")
            return False
