"""Request/response models — the API contract from docs/project3b-iot-gateway.md."""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

DeviceStatus = Literal["registered", "online", "offline", "suspended"]


class RegisterRequest(BaseModel):
    device_id: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9][a-z0-9\-]+$")
    device_type: str = Field(min_length=3, max_length=64)
    metadata: Dict[str, str] = Field(default_factory=dict, max_length=10)


class RegisterResponse(BaseModel):
    device_id: str
    api_key: str  # shown exactly once — only the bcrypt hash is stored
    status: DeviceStatus


class AuthRequest(BaseModel):
    api_key: str = Field(min_length=10, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: Literal["Bearer"] = "Bearer"


class MessageRequest(BaseModel):
    device_id: str = Field(min_length=3, max_length=64)
    payload: Dict[str, Any] = Field(min_length=1)
    timestamp: datetime


class MessageResponse(BaseModel):
    message_id: str
    status: Literal["queued"] = "queued"


class DeviceStatusResponse(BaseModel):
    device_id: str
    status: DeviceStatus
    last_seen: Optional[str] = None
    rate_limit_per_minute: int
    rate_limit_remaining: int
