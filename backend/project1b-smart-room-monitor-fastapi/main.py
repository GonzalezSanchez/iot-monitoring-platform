from fastapi import FastAPI, HTTPException

app = FastAPI(title="Smart Room Monitor API (FastAPI)")

# Dummy data for structure example
dummy_rooms = [
    {"room_id": "conference-a1", "occupancy": False},
]


@app.get("/rooms")
def get_rooms():
    return {"rooms": dummy_rooms}


@app.get("/rooms/{room_id}")
def get_room_detail(room_id: str):
    for room in dummy_rooms:
        if room["room_id"] == room_id:
            return {"room": room, "recent_events": [], "event_count": 0}
    raise HTTPException(status_code=404, detail="Room not found")
