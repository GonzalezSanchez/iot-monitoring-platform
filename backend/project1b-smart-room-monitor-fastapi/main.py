from typing import List

from fastapi import FastAPI, HTTPException
from models.room import Room
from repositories.room_repository import RoomRepository

app = FastAPI(title="Smart Room Monitor API (FastAPI)")

room_repo = RoomRepository()


@app.get("/rooms", response_model=List[Room])
def get_rooms():
    try:
        # Hier zou je normaal room_repo.list_rooms() gebruiken
        # Voor nu een lege lijst of mock
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rooms/{room_id}", response_model=Room)
def get_room_detail(room_id: str):
    try:
        # Hier zou je normaal room_repo.get_room(room_id) gebruiken
        # Voor nu een 404
        raise HTTPException(status_code=404, detail="Room not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
