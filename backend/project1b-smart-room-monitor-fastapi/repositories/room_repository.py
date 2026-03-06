"""
Room Repository
Handles DynamoDB operations for room status
"""
import logging
import os
from typing import List, Optional

import boto3
from models.room import Room

logger = logging.getLogger(__name__)


class RoomRepository:
    """Repository for room status in DynamoDB"""

    def __init__(self, dynamodb_resource=None, table_name: Optional[str] = None):
        """
        Initialize RoomRepository with dependency injection

        Args:
            dynamodb_resource: boto3 DynamoDB resource (creates default if None)
            table_name: DynamoDB table name (uses env var if None)
        """
        self.table_name = table_name or os.getenv("DYNAMODB_TABLE_ROOMS", "RoomStatus")

        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            self.dynamodb = boto3.resource(
                "dynamodb",
                endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
                region_name=os.getenv("AWS_REGION", "eu-west-1"),
            )

        self.table = self.dynamodb.Table(self.table_name)

    def get_room(self, room_id: str) -> Optional[dict]:
        """
        Get a single room by ID.

        Args:
            room_id: Unique room identifier

        Returns:
            Room item dict if found, None otherwise
        """
        logger.debug("Fetching room: %s", room_id)
        response = self.table.get_item(Key={"room_id": room_id})
        item = response.get("Item")
        if item:
            logger.debug("Room found: %s", room_id)
        else:
            logger.debug("Room not found: %s", room_id)
        return item  # type: ignore[return-value]

    def save_room(self, room: Room) -> None:
        """
        Save or update a room in DynamoDB.

        Args:
            room: Room instance to persist
        """
        logger.debug("Saving room: %s", room.room_id)
        self.table.put_item(Item=room.to_dynamodb_item())
        logger.info("Room saved: %s", room.room_id)

    def list_rooms(self) -> List[dict]:
        """
        List all rooms (scan — suitable for small datasets).

        Returns:
            List of room item dicts
        """
        logger.debug("Listing all rooms")
        response = self.table.scan()
        items: List[dict] = response.get("Items", [])
        logger.info("Retrieved %d rooms", len(items))
        return items
