"""Gateway API tests — the 3b-1 test contract (docs/project3-prd.md §7)."""

import json

import boto3

from gateway import config
from tests.conftest import auth_device, register_device

MSG = {
    "device_id": "sensor-001",
    "payload": {"temperature": 22.5, "humidity": 45},
    "timestamp": "2026-07-05T10:00:00Z",
}


def _stored_item(device_id="sensor-001"):
    table = boto3.resource("dynamodb", region_name=config.AWS_REGION).Table(config.DEVICES_TABLE)
    return table.get_item(Key={"device_id": device_id}).get("Item")


def _suspend(device_id="sensor-001"):
    table = boto3.resource("dynamodb", region_name=config.AWS_REGION).Table(config.DEVICES_TABLE)
    table.update_item(
        Key={"device_id": device_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "suspended"},
    )


# --- register ---------------------------------------------------------------


def test_register_returns_key_once_and_stores_only_hash(client):
    api_key = register_device(client)
    item = _stored_item()
    assert api_key.startswith("p3-")
    assert api_key not in json.dumps(item, default=str)  # plaintext never stored
    assert item["api_key_hash"].startswith("$2b$")


def test_register_same_device_twice_conflicts(client):
    register_device(client)
    resp = client.post(
        "/devices/register",
        json={"device_id": "sensor-001", "device_type": "temperature_sensor", "metadata": {}},
    )
    assert resp.status_code == 409


# --- auth -------------------------------------------------------------------


def test_auth_valid_key_returns_jwt(client):
    api_key = register_device(client)
    resp = client.post("/devices/sensor-001/auth", json={"api_key": api_key})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == config.JWT_EXPIRY_SECONDS


def test_auth_wrong_key_is_401(client):
    register_device(client)
    resp = client.post("/devices/sensor-001/auth", json={"api_key": "p3-" + "0" * 32})
    assert resp.status_code == 401


def test_auth_suspended_device_is_403(client):
    api_key = register_device(client)
    _suspend()
    resp = client.post("/devices/sensor-001/auth", json={"api_key": api_key})
    assert resp.status_code == 403


# --- messages ---------------------------------------------------------------


def test_message_produced_with_device_key(client):
    api_key = register_device(client)
    token = auth_device(client, "sensor-001", api_key)
    resp = client.post("/messages", json=MSG, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued"

    [sent] = client.fake_producer.sent
    assert sent["topic"] == config.TOPIC_SENSOR_EVENTS
    assert sent["key"] == b"sensor-001"
    event = json.loads(sent["value"])
    assert event["schema_version"] == config.SCHEMA_VERSION
    assert event["payload"] == {"temperature": 22.5, "humidity": 45}
    assert event["device_type"] == "temperature_sensor"


def test_message_without_token_is_401(client):
    assert client.post("/messages", json=MSG).status_code == 401


def test_message_with_garbage_token_is_401(client):
    resp = client.post("/messages", json=MSG, headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


def test_message_for_other_device_is_403(client):
    api_key = register_device(client)
    token = auth_device(client, "sensor-001", api_key)
    other = dict(MSG, device_id="sensor-999")
    resp = client.post("/messages", json=other, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_message_missing_fields_is_422(client):
    api_key = register_device(client)
    token = auth_device(client, "sensor-001", api_key)
    resp = client.post(
        "/messages", json={"device_id": "sensor-001"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422


def test_message_oversized_payload_is_422(client):
    api_key = register_device(client)
    token = auth_device(client, "sensor-001", api_key)
    big = dict(MSG, payload={f"field_{i}": i for i in range(config.MAX_PAYLOAD_FIELDS + 1)})
    resp = client.post("/messages", json=big, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


def test_rate_limit_blocks_one_device_not_another(client, monkeypatch):
    from gateway.rate_limiter import RateLimiter

    client.app.state.limiter = RateLimiter(default_per_minute=2, per_type={})

    key_a = register_device(client, "sensor-a")
    key_b = register_device(client, "sensor-b")
    token_a = auth_device(client, "sensor-a", key_a)
    token_b = auth_device(client, "sensor-b", key_b)

    msg_a = dict(MSG, device_id="sensor-a")
    msg_b = dict(MSG, device_id="sensor-b")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    assert client.post("/messages", json=msg_a, headers=headers_a).status_code == 202
    assert client.post("/messages", json=msg_a, headers=headers_a).status_code == 202
    assert client.post("/messages", json=msg_a, headers=headers_a).status_code == 429  # A blocked
    assert client.post("/messages", json=msg_b, headers=headers_b).status_code == 202  # B fine


def test_message_when_kafka_down_is_503(client):
    api_key = register_device(client)
    token = auth_device(client, "sensor-001", api_key)
    client.app.state.producer = None
    resp = client.post("/messages", json=MSG, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503


# --- status & health --------------------------------------------------------


def test_status_reports_rate_limit(client):
    api_key = register_device(client)
    token = auth_device(client, "sensor-001", api_key)
    resp = client.get("/devices/sensor-001/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "online"
    assert body["rate_limit_remaining"] == body["rate_limit_per_minute"]


def test_status_for_other_device_is_403(client):
    api_key = register_device(client)
    token = auth_device(client, "sensor-001", api_key)
    resp = client.get("/devices/sensor-999/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_health_reports_kafka_flag(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["kafka_connected"] is True  # fake producer injected
