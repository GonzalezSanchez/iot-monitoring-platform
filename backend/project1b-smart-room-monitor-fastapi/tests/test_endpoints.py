from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_get_rooms_empty():
    response = client.get("/rooms")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_events_empty():
    response = client.get("/events")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_post_event_and_get_events():
    # Maak een event aan
    event_data = {
        "room_id": "room-1",
        "sensor_type": "temperature",
        "value": 21.5,
        "timestamp": "2026-01-15T12:00:00",
    }
    post_resp = client.post("/events", json=event_data)
    assert post_resp.status_code == 201
    data = post_resp.json()
    assert data["room_id"] == "room-1"
    assert data["sensor_type"] == "temperature"
    # Haal events op, moet minstens 1 bevatten
    get_resp = client.get("/events?room_id=room-1")
    assert get_resp.status_code == 200
    events = get_resp.json()
    assert any(e["room_id"] == "room-1" for e in events)


def test_get_room_detail_404():
    response = client.get("/rooms/nonexistent-room")
    assert response.status_code == 404
    assert response.json()["detail"] == "Room not found"
