"""Security unit tests — API keys and JWTs (docs/project3-prd.md §5, §7 3b-1)."""

import time

import pytest
from jose import JWTError, jwt

from gateway import config, security


def test_api_key_has_prefix_and_is_unique():
    a, b = security.generate_api_key(), security.generate_api_key()
    assert a.startswith("p3-") and b.startswith("p3-")
    assert a != b


def test_api_key_hash_roundtrip():
    key = security.generate_api_key()
    hashed = security.hash_api_key(key)
    assert hashed != key
    assert security.verify_api_key(key, hashed)
    assert not security.verify_api_key("p3-wrong", hashed)


def test_jwt_roundtrip_and_expiry_claim():
    token = security.issue_token("sensor-001")
    assert security.verify_token(token) == "sensor-001"
    claims = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    assert claims["exp"] - claims["iat"] == config.JWT_EXPIRY_SECONDS


def test_expired_jwt_rejected():
    claims = {"sub": "sensor-001", "iat": int(time.time()) - 7200, "exp": int(time.time()) - 3600}
    expired = jwt.encode(claims, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    with pytest.raises(JWTError):
        security.verify_token(expired)


def test_tampered_jwt_rejected():
    token = security.issue_token("sensor-001")
    with pytest.raises(JWTError):
        security.verify_token(token[:-2] + "xx")
