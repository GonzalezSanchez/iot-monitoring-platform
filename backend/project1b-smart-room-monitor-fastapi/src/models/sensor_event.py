"""
Sensor Event Model
Represents a single sensor reading event
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from ulid import ULID


class SensorEvent(BaseModel):
    """Sensor event data model"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "room_id": "room-101",
                "sensor_type": "temperature",
                "value": 24.5,
                "timestamp": "2025-01-15T10:30:00Z",
            }
        }
    )

    event_id: str = Field(default_factory=lambda: str(ULID()))
    room_id: str = Field(..., min_length=1, max_length=50)
    sensor_type: str = Field(..., pattern="^(temperature|motion|occupancy|humidity)$")
    value: float
    unit: Optional[str] = None
    timestamp: datetime
    status: str = Field(default="normal", pattern="^(normal|warning|alert)$")

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v: object) -> object:
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    @model_validator(mode="after")
    def set_unit(self) -> "SensorEvent":
        """Auto-set unit based on sensor type"""
        if self.unit is not None:
            return self
        units = {
            "temperature": "°C",
            "humidity": "%",
            "occupancy": "people",
            "motion": "boolean",
        }
        self.unit = units.get(self.sensor_type, "unknown")
        return self

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format, ensuring float values are Decimal for DynamoDB"""
        from decimal import Decimal

        return {
            "room_id": self.room_id,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id,
            "sensor_type": self.sensor_type,
            "value": Decimal(str(self.value)) if isinstance(self.value, float) else self.value,
            "unit": self.unit,
            "status": self.status,
        }
