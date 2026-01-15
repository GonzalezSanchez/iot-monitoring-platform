"""
Script: add_test_room_local.py
Voegt een testkamer toe aan de DynamoDB RoomStatus tabel voor demo/testdoeleinden (DynamoDB Local).
Gebruik: python add_test_room_local.py
Zorg dat DynamoDB Local draait op poort 8001.
"""

from datetime import datetime, timezone
from decimal import Decimal

import boto3

# DynamoDB Local resource en tabel
# Endpoint aangepast voor lokale DynamoDB

dynamodb = boto3.resource(
    "dynamodb", region_name="eu-north-1", endpoint_url="http://localhost:8001"
)
table = dynamodb.Table("dev-RoomStatus")

# Testkamer-item
item = {
    "room_id": "conference-a1",
    "name": "Conference Room A1",
    "status": "active",
    "last_update": datetime.now(timezone.utc).isoformat(),
    "current_state": {
        "temperature": Decimal("22.5"),
        "motion": True,
        "occupancy": 5,
        "humidity": Decimal("45.0"),
    },
    "alert_count_24h": 0,
}

# Voeg item toe aan DynamoDB Local
try:
    response = table.put_item(Item=item)
    print("Testkamer toegevoegd:", response)
except Exception as e:
    print("Fout bij toevoegen testkamer:", e)
