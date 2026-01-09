"""
Sensor Event Model
Represents a single sensor reading event
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class SensorEvent(BaseModel):
    """Sensor event data model"""

    event_id: Optional[str] = None
    room_id: str = Field(..., min_length=1, max_length=50)
    sensor_type: str = Field(..., pattern="^(temperature|motion|occupancy|humidity)$")
    value: float
    unit: Optional[str] = None
    timestamp: datetime
    status: str = Field(default="normal", pattern="^(normal|warning|alert)$")

    @validator("timestamp", pre=True)
    def parse_timestamp(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    @validator("unit", always=True)
    def set_unit(cls, v, values):
        """Auto-set unit based on sensor type"""
        if v is not None:
            return v

        sensor_type = values.get("sensor_type")
        units = {
            "temperature": "°C",
            "humidity": "%",
            "occupancy": "people",
            "motion": "boolean",
        }
        return units.get(sensor_type, "unknown")

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format"""
        return {
            "room_id": self.room_id,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id or f"{self.room_id}_{self.timestamp.timestamp()}",
            "sensor_type": self.sensor_type,
            "value": self.value,
            "unit": self.unit,
            "status": self.status,
        }

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
