"""Project 3b-1 — device gateway (docs/project3-prd.md §6–§7).

Flow: register (api key, shown once) → auth (key → 1h JWT) → messages
(Bearer JWT → validate → rate-limit → produce to Kafka, key = device_id).
"""

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Tuple

from aiokafka import AIOKafkaProducer
from fastapi import Depends, FastAPI, HTTPException, Request
from jose import JWTError

from common.models import (
    AuthRequest,
    AuthResponse,
    DeviceStatusResponse,
    MessageRequest,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
)
from gateway import config, repository, security
from gateway.rate_limiter import RateLimiter

logger = logging.getLogger("gateway")

# device_id -> (device item, cached_at); keeps the message hot path off DynamoDB
_device_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}


async def _cached_device(device_id: str) -> Optional[Dict[str, Any]]:
    cached = _device_cache.get(device_id)
    if cached and time.monotonic() - cached[1] < config.DEVICE_CACHE_TTL_SECONDS:
        return cached[0]
    device = await asyncio.to_thread(repository.get_device, device_id)
    if device:
        _device_cache[device_id] = (device, time.monotonic())
    return device


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not set — the gateway refuses to start without it")
    limits = config.load_rate_limits()
    app.state.limiter = RateLimiter(limits["default"], limits["per_type"])
    app.state.producer = None
    try:
        producer = AIOKafkaProducer(bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS)
        await producer.start()
        app.state.producer = producer
        logger.info("Kafka producer connected to %s", config.KAFKA_BOOTSTRAP_SERVERS)
    except Exception:
        logger.warning("Kafka not reachable at startup — /messages will 503 until it is")
    yield
    if app.state.producer:
        await app.state.producer.stop()


app = FastAPI(title="IoT Device Gateway", lifespan=lifespan)


def authenticated_device(request: Request) -> str:
    """Extract and verify the Bearer JWT; return the device_id (sub)."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        return security.verify_token(header.removeprefix("Bearer "))
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@app.get("/health")
async def health(request: Request):
    producer = request.app.state.producer
    return {
        "status": "ok",
        "service": "gateway",
        "kafka_connected": producer is not None,
    }


@app.post("/devices/register", response_model=RegisterResponse, status_code=201)
async def register(body: RegisterRequest):
    api_key = security.generate_api_key()
    api_key_hash = security.hash_api_key(api_key)
    try:
        await asyncio.to_thread(
            repository.create_device, body.device_id, body.device_type, api_key_hash, body.metadata
        )
    except repository.DeviceAlreadyExists:
        raise HTTPException(status_code=409, detail="Device already registered")
    return RegisterResponse(device_id=body.device_id, api_key=api_key, status="registered")


@app.post("/devices/{device_id}/auth", response_model=AuthResponse)
async def auth(device_id: str, body: AuthRequest):
    device = await asyncio.to_thread(repository.get_device, device_id)
    if not device or not security.verify_api_key(body.api_key, device["api_key_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if device["status"] == "suspended":
        raise HTTPException(status_code=403, detail="Device suspended")
    await asyncio.to_thread(repository.touch_device, device_id)
    _device_cache.pop(device_id, None)
    return AuthResponse(access_token=security.issue_token(device_id), expires_in=config.JWT_EXPIRY_SECONDS)


@app.post("/messages", response_model=MessageResponse, status_code=202)
async def messages(
    body: MessageRequest, request: Request, token_device: str = Depends(authenticated_device)
):
    if body.device_id != token_device:
        raise HTTPException(status_code=403, detail="Token does not match device_id")
    if len(body.payload) > config.MAX_PAYLOAD_FIELDS:
        raise HTTPException(status_code=422, detail="Payload too large")

    device = await _cached_device(token_device)
    if not device:
        raise HTTPException(status_code=401, detail="Unknown device")
    if device["status"] == "suspended":
        raise HTTPException(status_code=403, detail="Device suspended")

    limiter: RateLimiter = request.app.state.limiter
    if not limiter.allow(token_device, device["device_type"]):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    producer = request.app.state.producer
    if producer is None:
        raise HTTPException(status_code=503, detail="Message broker unavailable")

    message_id = str(uuid.uuid4())
    event = {
        "schema_version": config.SCHEMA_VERSION,
        "message_id": message_id,
        "device_id": body.device_id,
        "device_type": device["device_type"],
        "payload": body.payload,
        "timestamp": body.timestamp.isoformat(),
        "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    await producer.send_and_wait(
        config.TOPIC_SENSOR_EVENTS,
        json.dumps(event).encode(),
        key=body.device_id.encode(),
    )
    return MessageResponse(message_id=message_id)


@app.get("/devices/{device_id}/status", response_model=DeviceStatusResponse)
async def device_status(
    device_id: str, request: Request, token_device: str = Depends(authenticated_device)
):
    if device_id != token_device:
        raise HTTPException(status_code=403, detail="Token does not match device_id")
    device = await asyncio.to_thread(repository.get_device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Unknown device")
    limiter: RateLimiter = request.app.state.limiter
    return DeviceStatusResponse(
        device_id=device_id,
        status=device["status"],
        last_seen=device.get("last_seen"),
        rate_limit_per_minute=limiter.limit_for(device["device_type"]),
        rate_limit_remaining=limiter.remaining(device_id, device["device_type"]),
    )
