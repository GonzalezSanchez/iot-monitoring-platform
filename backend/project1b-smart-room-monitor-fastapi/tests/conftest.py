import boto3
import pytest
from moto import mock_dynamodb

DYNAMODB_TABLE_ROOMS = "RoomStatus"
DYNAMODB_TABLE_EVENTS = "SensorEvents"


@pytest.fixture(autouse=True)
def dynamodb_mock(monkeypatch):
    with mock_dynamodb():
        # Maak DynamoDB resource en tables aan
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
        # Rooms table
        table_rooms = dynamodb.create_table(
            TableName=DYNAMODB_TABLE_ROOMS,
            KeySchema=[{"AttributeName": "room_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "room_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table_rooms.wait_until_exists()
        # Events table
        table_events = dynamodb.create_table(
            TableName=DYNAMODB_TABLE_EVENTS,
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
        table_events.wait_until_exists()
        # Patch de omgevingsvariabelen zodat de app deze tables gebruikt
        monkeypatch.setenv("DYNAMODB_TABLE_ROOMS", DYNAMODB_TABLE_ROOMS)
        monkeypatch.setenv("DYNAMODB_TABLE_EVENTS", DYNAMODB_TABLE_EVENTS)
        yield
