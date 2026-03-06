"""
Sensor Event Model
Represents a single sensor reading event
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SensorEvent(BaseModel):
    """Sensor event data model"""

    event_id: Optional[str] = None
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
            "event_id": self.event_id or f"{self.room_id}_{self.timestamp.timestamp()}",
            "sensor_type": self.sensor_type,
            "value": Decimal(str(self.value))
            if isinstance(self.value, float)
            else self.value,
            "unit": self.unit,
            "status": self.status,
        }
