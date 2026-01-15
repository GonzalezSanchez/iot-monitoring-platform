import os
from typing import Optional

import boto3


class EventRepository:
    """Repository for sensor events in DynamoDB"""

    def __init__(self, dynamodb_resource=None, table_name: Optional[str] = None):
        """
        Initialize EventRepository with dependency injection

        Args:
            dynamodb_resource: boto3 DynamoDB resource (creates default if None)
            table_name: DynamoDB table name (uses env var if None)
        """
        self.table_name = table_name or os.getenv(
            "DYNAMODB_TABLE_EVENTS", "SensorEvents"
        )

        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            self.dynamodb = boto3.resource(
                "dynamodb",
                endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
                region_name=os.getenv("AWS_REGION", "eu-west-1"),
            )

        self.table = self.dynamodb.Table(self.table_name)

    def list_events(self, room_id: Optional[str] = None) -> list:
        """
        Haal events op uit DynamoDB. Optioneel filteren op room_id.
        Returns:
            List[dict]: Lijst van event-items
        """
        if room_id:
            # Query op room_id (partition key)
            response = self.table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("room_id").eq(
                    room_id
                )
            )
            return response.get("Items", [])
        else:
            # Scan alle events (alleen voor test/kleine datasets)
            response = self.table.scan()
            return response.get("Items", [])

    def save_event(self, event_item: dict):
        """
        Sla een event op in DynamoDB.
        Args:
            event_item (dict): Event data in DynamoDB formaat
        Returns:
            dict: DynamoDB response
        """
        try:
            print(f"[DEBUG] put_item to table {self.table_name}: {event_item}")
            response = self.table.put_item(Item=event_item)
            print(f"[DEBUG] put_item response: {response}")
            return response
        except Exception as e:
            print(f"[ERROR] Exception in save_event: {e}")
            raise
