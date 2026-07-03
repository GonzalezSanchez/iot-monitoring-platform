import logging
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP

from models.lakehouse import Anomaly, DimRoom, LakehouseSummary
from models.room import Room
from models.sensor_event import SensorEvent
from repositories import lakehouse_repository
from repositories.event_repository import EventRepository
from repositories.room_repository import RoomRepository
from services.event_service import EventService, EventServiceError

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

tags_metadata = [
    {
        "name": "Health",
        "description": "Service health check. Use this to verify the API is running.",
    },
    {
        "name": "Lakehouse",
        "description": (
            "Live data from the Azure Databricks Gold layer (project 2c). "
            "Queries the SQL Warehouse — first request may take 30-60s if the warehouse is cold."
        ),
    },
    {
        "name": "Events",
        "description": (
            "Ingest and query sensor events. "
            "Each event represents a single sensor reading "
            "(temperature, humidity, occupancy, or motion). "
            "Events are processed through anomaly detection before being stored."
        ),
    },
    {
        "name": "Rooms",
        "description": (
            "Query room state. "
            "Each room aggregates the latest readings from all its sensors. "
            "Room status reflects the worst active alert across all sensor types."
        ),
    },
]

app = FastAPI(
    title="Smart Room Monitor API",
    description=(
        "Real-time IoT sensor monitoring for conference rooms. "
        "Ingests sensor events (temperature, humidity, occupancy, motion), "
        "runs anomaly detection, and tracks room state."
    ),
    version="1.0.0",
    contact={
        "name": "Álvaro González Sánchez",
        "email": "a.gonzalez.sanchez@gmail.com",
        "url": "https://gonzalezsanchez.dev",
    },
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://iot.gonzalezsanchez.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

room_repo = RoomRepository()
event_repo = EventRepository()
event_service = EventService(event_repo, room_repo)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health", response_model=Dict[str, Any], tags=["Health"])
def health_check() -> Dict[str, Any]:
    """Returns API health status. Useful for load balancers and monitoring."""
    return {"status": "ok", "service": "smart-room-monitor"}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@app.get("/events", response_model=List[SensorEvent], tags=["Events"], operation_id="get_events")
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


@app.get("/rooms", response_model=List[Room], tags=["Rooms"], operation_id="get_rooms")
def get_rooms() -> List[Room]:
    """List all monitored rooms with their current sensor state."""
    try:
        items = room_repo.list_rooms()
        return [Room.from_dynamodb_item(item) for item in items]
    except Exception as e:
        logger.error("Failed to list rooms: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rooms/{room_id}", response_model=Room, tags=["Rooms"], operation_id="get_room")
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


@app.get(
    "/rooms/{room_id}/events",
    response_model=List[SensorEvent],
    tags=["Rooms"],
    operation_id="get_room_events",
)
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


# ---------------------------------------------------------------------------
# Lakehouse (project 2c — Azure Databricks Gold layer)
# ---------------------------------------------------------------------------


def _lakehouse_configured() -> bool:
    return all(
        os.getenv(k) for k in ("DATABRICKS_HOST", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN")
    )


@app.get(
    "/lakehouse/summary",
    response_model=LakehouseSummary,
    tags=["Lakehouse"],
    operation_id="get_lakehouse_summary",
)
def get_lakehouse_summary() -> LakehouseSummary:
    """Total event count, anomaly count, and last pipeline run time from the Gold layer."""
    if not _lakehouse_configured():
        raise HTTPException(status_code=503, detail="Lakehouse not configured on this server")
    try:
        data = lakehouse_repository.get_summary()
        return LakehouseSummary(**data)
    except Exception as e:
        logger.error("Lakehouse summary failed: %s", e)
        raise HTTPException(status_code=503, detail=f"SQL Warehouse unavailable: {e}")


@app.get(
    "/lakehouse/anomalies",
    response_model=List[Anomaly],
    tags=["Lakehouse"],
    operation_id="get_lakehouse_anomalies",
)
def get_lakehouse_anomalies(limit: int = 50) -> List[Anomaly]:
    """Recent anomalies from fact_anomalies (is_anomaly=true), newest first."""
    if not _lakehouse_configured():
        raise HTTPException(status_code=503, detail="Lakehouse not configured on this server")
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    try:
        rows = lakehouse_repository.get_anomalies(limit=limit)
        return [Anomaly(**r) for r in rows]
    except Exception as e:
        logger.error("Lakehouse anomalies failed: %s", e)
        raise HTTPException(status_code=503, detail=f"SQL Warehouse unavailable: {e}")


@app.get(
    "/lakehouse/rooms",
    response_model=List[DimRoom],
    tags=["Lakehouse"],
    operation_id="get_lakehouse_rooms",
)
def get_lakehouse_rooms() -> List[DimRoom]:
    """Room metadata joined with building info from the Gold dimension tables."""
    if not _lakehouse_configured():
        raise HTTPException(status_code=503, detail="Lakehouse not configured on this server")
    try:
        rows = lakehouse_repository.get_rooms()
        return [DimRoom(**r) for r in rows]
    except Exception as e:
        logger.error("Lakehouse rooms failed: %s", e)
        raise HTTPException(status_code=503, detail=f"SQL Warehouse unavailable: {e}")


# ---------------------------------------------------------------------------
# MCP (project 4a — tool surface for the AI assistant)
# ---------------------------------------------------------------------------

# Allowlist, never a denylist: a route added later must not silently become a
# tool. Writing routes (POST /events) stay out so prompt injection cannot write.
# /mcp is internal-only: the nginx location regex must never include it.
MCP_TOOL_ALLOWLIST = [
    "get_rooms",
    "get_room",
    "get_room_events",
    "get_events",
    "get_lakehouse_summary",
    "get_lakehouse_anomalies",
    "get_lakehouse_rooms",
]

mcp = FastApiMCP(
    app,
    name="Smart Room Monitor MCP",
    description="Read-only MCP tools over the Smart Room Monitor API.",
    include_operations=MCP_TOOL_ALLOWLIST,
)
mcp.mount_http()
