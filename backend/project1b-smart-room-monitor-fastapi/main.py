import logging
from typing import List, Optional

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

app = FastAPI(title="Smart Room Monitor API (FastAPI)")

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


@app.get("/events", response_model=List[SensorEvent])
def get_events(room_id: Optional[str] = None) -> List[SensorEvent]:
    try:
        items = event_repo.list_events(room_id=room_id)
        return [SensorEvent(**item) for item in items]
    except Exception as e:
        logger.error("Failed to list events: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/events", response_model=SensorEvent, status_code=201)
def create_event(event: SensorEvent) -> SensorEvent:
    try:
        event_service.process_event(event)
        return event
    except EventServiceError as e:
        logger.error("Event processing failed: %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in create_event: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rooms", response_model=List[Room])
def get_rooms() -> List[Room]:
    try:
        items = room_repo.list_rooms()
        return [Room.from_dynamodb_item(item) for item in items]
    except Exception as e:
        logger.error("Failed to list rooms: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rooms/{room_id}", response_model=Room)
def get_room_detail(room_id: str) -> Room:
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
