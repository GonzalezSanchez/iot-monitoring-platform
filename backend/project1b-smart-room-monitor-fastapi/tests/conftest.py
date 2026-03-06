import boto3
import pytest
from moto import mock_dynamodb

DYNAMODB_TABLE_ROOMS = "RoomStatus"
DYNAMODB_TABLE_EVENTS = "SensorEvents"


@pytest.fixture(autouse=True)
def dynamodb_mock(monkeypatch):
    """
    Spin up a fresh moto DynamoDB mock for every test.

    load_dotenv() in main.py sets AWS_ENDPOINT_URL=http://localhost:8001 as a
    process env var, which makes boto3 bypass moto and try to reach the local
    DynamoDB container (which isn't running during tests). We remove that env var
    first so moto can intercept all DynamoDB calls.

    We also inject fresh moto-backed repository instances directly into the main
    module so every HTTP request in the test uses the in-memory mock.
    """
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)

    with mock_dynamodb():
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")

        # Create the two tables the app depends on
        dynamodb.create_table(
            TableName=DYNAMODB_TABLE_ROOMS,
            KeySchema=[{"AttributeName": "room_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "room_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        ).wait_until_exists()

        dynamodb.create_table(
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
        ).wait_until_exists()

        # Build fresh repos backed by the moto resource
        import main
        from repositories.event_repository import EventRepository
        from repositories.room_repository import RoomRepository
        from services.event_service import EventService

        event_repo = EventRepository(
            dynamodb_resource=dynamodb, table_name=DYNAMODB_TABLE_EVENTS
        )
        room_repo = RoomRepository(
            dynamodb_resource=dynamodb, table_name=DYNAMODB_TABLE_ROOMS
        )
        svc = EventService(event_repo=event_repo, room_repo=room_repo)

        # Patch the module-level instances so every request uses the moto mock
        monkeypatch.setattr(main, "event_repo", event_repo)
        monkeypatch.setattr(main, "room_repo", room_repo)
        monkeypatch.setattr(main, "event_service", svc)

        yield
