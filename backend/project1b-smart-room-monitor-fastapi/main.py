import logging
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models.room import Room
from models.sensor_event import SensorEvent
from repositories.event_repository import EventRepository
from repositories.room_repository import RoomRepository
from services.event_service import EventService, EventServiceError

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Smart Room Monitor API",
    description=(
        "Real-time IoT sensor monitoring for conference rooms. "
        "Ingests sensor events (temperature, humidity, occupancy, motion), "
        "runs anomaly detection, and tracks room state."
    ),
    version="1.0.0",
    contact={"name": "Álvaro González Sánchez"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

room_repo = RoomRepository()
event_repo = EventRepository()
event_service = EventService(event_repo=event_repo, room_repo=room_repo)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Health"])
def health_check() -> Dict[str, Any]:
    """Returns API health status. Useful for load balancers and monitoring."""
    return {"status": "ok", "service": "smart-room-monitor"}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@app.get("/events", response_model=List[SensorEvent], tags=["Events"])
def get_events(room_id: Optional[str] = None) -> List[SensorEvent]:
    """
    List sensor events.

    - Without `room_id`: returns all events (scan — use for small datasets / demos).
    - With `room_id`: returns events for that room only (efficient DynamoDB query).
    """
    try:
        items = event_repo.list_events(room_id=room_id)
        return [SensorEvent(**item) for item in items]
    except Exception as e:
        logger.error("Failed to list events: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/events", response_model=SensorEvent, status_code=201, tags=["Events"])
def create_event(event: SensorEvent) -> SensorEvent:
    """
    Ingest a sensor event.

    Runs the full processing pipeline:
    1. Anomaly detection (sets `status` to `normal`, `warning`, or `alert`)
    2. Persists event to DynamoDB
    3. Updates room state (creates room record if it doesn't exist yet)
    """
    try:
        event_service.process_event(event)
        return event
    except EventServiceError as e:
        logger.error("Event processing failed: %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in create_event: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------


@app.get("/rooms", response_model=List[Room], tags=["Rooms"])
def get_rooms() -> List[Room]:
    """List all monitored rooms with their current sensor state."""
    try:
        items = room_repo.list_rooms()
        return [Room.from_dynamodb_item(item) for item in items]
    except Exception as e:
        logger.error("Failed to list rooms: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rooms/{room_id}", response_model=Room, tags=["Rooms"])
def get_room_detail(room_id: str) -> Room:
    """Get current state and status for a specific room."""
    try:
        item = room_repo.get_room(room_id)
        if not item:
            raise HTTPException(status_code=404, detail="Room not found")
        return Room.from_dynamodb_item(item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get room %s: %s", room_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rooms/{room_id}/events", response_model=List[SensorEvent], tags=["Rooms"])
def get_room_events(room_id: str) -> List[SensorEvent]:
    """
    Get all sensor events for a specific room.

    Returns events sorted by DynamoDB sort key (timestamp ascending).
    """
    try:
        item = room_repo.get_room(room_id)
        if not item:
            raise HTTPException(status_code=404, detail="Room not found")
        events = event_repo.list_events(room_id=room_id)
        return [SensorEvent(**e) for e in events]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get events for room %s: %s", room_id, e)
        raise HTTPException(status_code=500, detail=str(e))
