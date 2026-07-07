import os

# Test environment BEFORE the app modules load config
os.environ["JWT_SECRET"] = "test-secret-for-unit-tests-only"
os.environ["DEVICES_TABLE"] = "test-Devices"
os.environ["SENSOR_EVENTS_TABLE"] = "test-SensorEvents"
os.environ["ROOM_STATUS_TABLE"] = "test-RoomStatus"
os.environ["AWS_REGION"] = "eu-central-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "127.0.0.1:1"  # never reachable in tests

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from consumer import config as consumer_config
from gateway import config
from gateway import main as gateway_main


class FakeProducer:
    """Records what the gateway produces — no broker in unit tests."""

    def __init__(self):
        self.sent = []

    async def send_and_wait(self, topic, value, key=None):
        self.sent.append({"topic": topic, "value": value, "key": key})

    async def stop(self):
        pass


@pytest.fixture()
def client(monkeypatch):
    with mock_aws():
        boto3.resource("dynamodb", region_name=config.AWS_REGION).create_table(
            TableName=config.DEVICES_TABLE,
            KeySchema=[{"AttributeName": "device_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "device_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Kafka must never be contacted in unit tests
        async def no_connect(self):
            raise ConnectionError("no broker in tests")

        monkeypatch.setattr("aiokafka.AIOKafkaProducer.start", no_connect)
        gateway_main._device_cache.clear()

        with TestClient(gateway_main.app) as test_client:
            fake = FakeProducer()
            gateway_main.app.state.producer = fake
            test_client.fake_producer = fake
            yield test_client


@pytest.fixture()
def contract_tables():
    """moto versions of the shared contract tables the consumer writes."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=consumer_config.AWS_REGION)
        events = dynamodb.create_table(
            TableName=consumer_config.SENSOR_EVENTS_TABLE,
            KeySchema=[
                {"AttributeName": "room_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "room_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        rooms = dynamodb.create_table(
            TableName=consumer_config.ROOM_STATUS_TABLE,
            KeySchema=[{"AttributeName": "room_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "room_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield events, rooms


class FakeDlq:
    """Collects DLQ records the consumer produces in tests."""

    def __init__(self):
        self.records = []

    async def __call__(self, record: bytes):
        self.records.append(record)


def register_device(client, device_id="sensor-001", device_type="temperature_sensor"):
    resp = client.post(
        "/devices/register",
        json={"device_id": device_id, "device_type": device_type, "metadata": {"location": "lab"}},
    )
    assert resp.status_code == 201
    return resp.json()["api_key"]


def auth_device(client, device_id, api_key):
    resp = client.post(f"/devices/{device_id}/auth", json={"api_key": api_key})
    assert resp.status_code == 200
    return resp.json()["access_token"]
