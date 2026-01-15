"""
Room Model
Represents a monitored room with current state
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RoomState(BaseModel):
    """Current state of a room"""

    temperature: Optional[float] = None
    motion: Optional[bool] = None
    occupancy: Optional[int] = None
    humidity: Optional[float] = None


class Room(BaseModel):
    """Room data model"""

    room_id: str = Field(..., min_length=1, max_length=50)
    name: str
    status: str = Field(default="active", pattern="^(active|warning|alert|offline)$")
    last_update: datetime
    current_state: RoomState = Field(default_factory=RoomState)
    alert_count_24h: int = Field(default=0, ge=0)

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format"""
        return {
            "room_id": self.room_id,
            "name": self.name,
            "status": self.status,
            "last_update": self.last_update.isoformat(),
            "current_state": self.current_state.dict(exclude_none=True),
            "alert_count_24h": self.alert_count_24h,
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "Room":
        """Create Room from DynamoDB item"""
        return cls(
            room_id=item["room_id"],
            name=item["name"],
            status=item["status"],
            last_update=datetime.fromisoformat(item["last_update"]),
            current_state=RoomState(**item.get("current_state", {})),
            alert_count_24h=item.get("alert_count_24h", 0),
        )
