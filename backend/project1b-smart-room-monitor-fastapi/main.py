from typing import List, Optional

from fastapi import FastAPI, HTTPException
from models.room import Room
from models.sensor_event import SensorEvent
from repositories.event_repository import EventRepository
from repositories.room_repository import RoomRepository

app = FastAPI(title="Smart Room Monitor API (FastAPI)")
room_repo = RoomRepository()
event_repo = EventRepository()


@app.get("/events", response_model=List[SensorEvent])
def get_events(room_id: Optional[str] = None):
    try:
        items = event_repo.list_events(room_id=room_id)
        return [SensorEvent(**item) for item in items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/events", response_model=SensorEvent, status_code=201)
def create_event(event: SensorEvent):
    try:
        item = event.to_dynamodb_item()
        print(f"[DEBUG] Saving event item: {item}")
        event_repo.save_event(item)
        # Geef het event terug met gegenereerde event_id
        return SensorEvent(**item)
    except Exception as e:
        print(f"[ERROR] Exception in create_event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rooms", response_model=List[Room])
def get_rooms():
    try:
        items = room_repo.list_rooms()
        # Zet DynamoDB dicts om naar Room-models
        return [Room(**item) for item in items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rooms/{room_id}", response_model=Room)
def get_room_detail(room_id: str):
    try:
        item = room_repo.get_room(room_id)
        if not item:
            raise HTTPException(status_code=404, detail="Room not found")
        return Room(**item)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
