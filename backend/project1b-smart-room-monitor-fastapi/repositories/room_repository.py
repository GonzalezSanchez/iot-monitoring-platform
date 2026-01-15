import os
from typing import Optional

import boto3

"""
Room Repository
Handles DynamoDB operations for room status
"""


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
        Haal één room op uit DynamoDB op basis van room_id.
        Returns:
            dict | None: Room-item of None als niet gevonden
        """
        response = self.table.get_item(Key={"room_id": room_id})
        return response.get("Item")

    def save_room(self, room):
        raise NotImplementedError("save_room not yet implemented.")

    def list_rooms(self):
        """
        Haal alle rooms op uit DynamoDB.
        Returns:
            List[dict]: Lijst van room-items
        """
        response = self.table.scan()
        return response.get("Items", [])
