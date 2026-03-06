from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "smart-room-monitor"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def test_get_events_empty():
    response = client.get("/events")
    assert response.status_code == 200
    assert response.json() == []


def test_post_event_normal_temperature():
    """Normal temperature (21.5°C) should have status 'normal'."""
    event_data = {
        "room_id": "room-1",
        "sensor_type": "temperature",
        "value": 21.5,
        "timestamp": "2026-01-15T12:00:00",
    }
    response = client.post("/events", json=event_data)
    assert response.status_code == 201
    data = response.json()
    assert data["room_id"] == "room-1"
    assert data["sensor_type"] == "temperature"
    assert data["status"] == "normal"


def test_post_event_high_temperature_triggers_warning():
    """Temperature above 26°C should result in 'warning' status."""
    event_data = {
        "room_id": "room-2",
        "sensor_type": "temperature",
        "value": 28.0,
        "timestamp": "2026-01-15T12:00:00",
    }
    response = client.post("/events", json=event_data)
    assert response.status_code == 201
    assert response.json()["status"] == "warning"


def test_post_event_critical_temperature_triggers_alert():
    """Temperature >= 30°C should result in 'alert' status."""
    event_data = {
        "room_id": "room-3",
        "sensor_type": "temperature",
        "value": 32.0,
        "timestamp": "2026-01-15T12:00:00",
    }
    response = client.post("/events", json=event_data)
    assert response.status_code == 201
    assert response.json()["status"] == "alert"


def test_post_event_invalid_sensor_type():
    """Unknown sensor type should be rejected with 422."""
    event_data = {
        "room_id": "room-1",
        "sensor_type": "pressure",  # not in allowed types
        "value": 1013.0,
        "timestamp": "2026-01-15T12:00:00",
    }
    response = client.post("/events", json=event_data)
    assert response.status_code == 422


def test_post_event_and_get_events():
    """Posted event should be retrievable via GET /events?room_id=..."""
    event_data = {
        "room_id": "room-1",
        "sensor_type": "temperature",
        "value": 21.5,
        "timestamp": "2026-01-15T12:00:00",
    }
    client.post("/events", json=event_data)

    response = client.get("/events?room_id=room-1")
    assert response.status_code == 200
    events = response.json()
    assert any(e["room_id"] == "room-1" for e in events)


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------


def test_get_rooms_empty():
    response = client.get("/rooms")
    assert response.status_code == 200
    assert response.json() == []


def test_get_room_detail_404():
    response = client.get("/rooms/nonexistent-room")
    assert response.status_code == 404
    assert response.json()["detail"] == "Room not found"


def test_post_event_creates_room():
    """Posting an event should auto-create a room record."""
    event_data = {
        "room_id": "room-auto",
        "sensor_type": "temperature",
        "value": 22.0,
        "timestamp": "2026-01-15T12:00:00",
    }
    client.post("/events", json=event_data)

    response = client.get("/rooms/room-auto")
    assert response.status_code == 200
    room = response.json()
    assert room["room_id"] == "room-auto"
    assert room["current_state"]["temperature"] == 22.0


def test_get_room_events_404():
    """GET /rooms/{room_id}/events should 404 when room doesn't exist."""
    response = client.get("/rooms/nonexistent/events")
    assert response.status_code == 404


def test_get_room_events():
    """Events posted for a room should appear at GET /rooms/{room_id}/events."""
    event_data = {
        "room_id": "room-events",
        "sensor_type": "humidity",
        "value": 55.0,
        "timestamp": "2026-01-15T12:00:00",
    }
    client.post("/events", json=event_data)

    response = client.get("/rooms/room-events/events")
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["sensor_type"] == "humidity"
    assert events[0]["value"] == 55.0
