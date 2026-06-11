from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Anomaly(BaseModel):
    room_id: str
    sensor_type: str
    value: float
    z_score: float
    ts: datetime


class LakehouseSummary(BaseModel):
    total_events: int
    total_anomalies: int
    latest_event_ts: Optional[datetime]
    last_dbt_run: Optional[datetime]


class DimRoom(BaseModel):
    room_id: str
    room_name: str
    floor: int
    capacity: int
    building_name: str
    city: str
