"""
Script: create_roomstatus_table_local.py
Maakt de DynamoDB tabel 'dev-RoomStatus' aan in DynamoDB Local (poort 8001)
als deze nog niet bestaat.
Gebruik: python create_roomstatus_table_local.py
"""

import boto3
from botocore.exceptions import ClientError

# DynamoDB Local resource

dynamodb = boto3.resource(
    "dynamodb",
    region_name="eu-north-1",
    endpoint_url="http://localhost:8001",
)

table_name = "dev-RoomStatus"

try:
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "room_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "room_id", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    table.wait_until_exists()
    print(f"Tabel '{table_name}' aangemaakt.")
except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceInUseException":
        print(f"Tabel '{table_name}' bestaat al.")
    else:
        print("Fout bij aanmaken tabel:", e)
