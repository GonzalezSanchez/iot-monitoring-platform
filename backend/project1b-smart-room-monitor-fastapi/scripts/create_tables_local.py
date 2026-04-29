"""
Creates both DynamoDB tables in DynamoDB Local (port 8001).
Run this once after starting docker-compose.
"""

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource(
    "dynamodb",
    region_name="eu-central-1",
    endpoint_url="http://localhost:8001",
)

TABLES = [
    {
        "TableName": "dev-RoomStatus",
        "KeySchema": [{"AttributeName": "room_id", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "room_id", "AttributeType": "S"}],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "SensorEvents",
        "KeySchema": [
            {"AttributeName": "room_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "room_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
]

for table_def in TABLES:
    name = table_def["TableName"]
    try:
        table = dynamodb.create_table(**table_def)
        table.wait_until_exists()
        print(f"Created: {name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"Already exists: {name}")
        else:
            raise
