import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
TOPIC_SENSOR_EVENTS = os.getenv("TOPIC_SENSOR_EVENTS", "sensor-events")

DEVICES_TABLE = os.getenv("DEVICES_TABLE", "p3-prod-Devices")
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")

# JWT signing secret has no default on purpose — main.py fails fast when missing
# (docs/project3-prd.md §5.2).
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = int(os.getenv("JWT_EXPIRY_SECONDS", "3600"))

MAX_PAYLOAD_FIELDS = int(os.getenv("MAX_PAYLOAD_FIELDS", "20"))
DEVICE_CACHE_TTL_SECONDS = float(os.getenv("DEVICE_CACHE_TTL_SECONDS", "30"))

RATE_LIMITS_PATH = Path(
    os.getenv("RATE_LIMITS_PATH", str(Path(__file__).parents[2] / "config" / "rate_limits.yml"))
)

SCHEMA_VERSION = 1


def load_rate_limits() -> dict:
    """Per-device-type messages/minute limits (docs/project3-prd.md §5.3)."""
    with open(RATE_LIMITS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {
        "default": int(data["default_per_minute"]),
        "per_type": {k: int(v) for k, v in (data.get("per_device_type") or {}).items()},
    }
