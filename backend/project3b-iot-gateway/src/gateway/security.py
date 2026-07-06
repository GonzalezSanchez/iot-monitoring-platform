"""API keys and JWTs (docs/project3-prd.md §5.1–5.2)."""

import secrets
import time

import bcrypt
from jose import JWTError, jwt

from gateway import config

API_KEY_PREFIX = "p3-"


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_hex(32)


def hash_api_key(api_key: str) -> str:
    return bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()


def verify_api_key(api_key: str, api_key_hash: str) -> bool:
    try:
        return bcrypt.checkpw(api_key.encode(), api_key_hash.encode())
    except ValueError:
        return False


def issue_token(device_id: str) -> str:
    now = int(time.time())
    claims = {"sub": device_id, "iat": now, "exp": now + config.JWT_EXPIRY_SECONDS}
    return jwt.encode(claims, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def verify_token(token: str) -> str:
    """Return the device_id from a valid token; raise JWTError otherwise."""
    claims = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    device_id = claims.get("sub")
    if not device_id:
        raise JWTError("missing sub claim")
    return str(device_id)
