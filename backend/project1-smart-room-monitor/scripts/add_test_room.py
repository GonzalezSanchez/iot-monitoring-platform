"""
Script: add_test_room.py
Voegt een testkamer toe aan de DynamoDB RoomStatus tabel voor demo/testdoeleinden.
Gebruik: python add_test_room.py
Zorg dat je AWS credentials en regio correct zijn ingesteld.
"""

from datetime import datetime, timezone
from decimal import Decimal

import boto3

# DynamoDB resource en tabel
# Pas 'dev-RoomStatus' aan indien je een andere omgeving gebruikt

dynamodb = boto3.resource("dynamodb", region_name="eu-north-1")
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

# Voeg item toe aan DynamoDB
try:
    response = table.put_item(Item=item)
    print("Testkamer toegevoegd:", response)
except Exception as e:
    print("Fout bij toevoegen testkamer:", e)
