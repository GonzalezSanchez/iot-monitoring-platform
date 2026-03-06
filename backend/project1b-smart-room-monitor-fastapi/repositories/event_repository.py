import logging
import os
from typing import List, Optional

import boto3

logger = logging.getLogger(__name__)


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

    def list_events(self, room_id: Optional[str] = None) -> List[dict]:
        """
        List events, optionally filtered by room_id.

        Args:
            room_id: If provided, query events for this room only

        Returns:
            List of event item dicts
        """
        if room_id:
            logger.debug("Querying events for room: %s", room_id)
            response = self.table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("room_id").eq(
                    room_id
                )
            )
        else:
            logger.debug("Scanning all events")
            response = self.table.scan()

        items: List[dict] = response.get("Items", [])
        logger.info("Retrieved %d events", len(items))
        return items

    def save_event(self, event_item: dict) -> None:
        """
        Save an event to DynamoDB.

        Args:
            event_item: Event data in DynamoDB item format
        """
        logger.debug("Saving event to table %s: %s", self.table_name, event_item)
        self.table.put_item(Item=event_item)
        logger.info("Event saved: %s", event_item.get("event_id"))
