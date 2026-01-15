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

    def save_event(self, event_item):
        raise NotImplementedError("save_event not yet implemented.")
