"""
Event Repository
Handles DynamoDB operations for sensor events
"""
import logging
import os
from datetime import datetime
from typing import List, Optional
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# Configure logger
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
        # Allow table name override for testing or multi-environment use
        self.table_name = table_name or os.getenv(
            "DYNAMODB_TABLE_EVENTS", "SensorEvents"
        )

        # Use injected resource or create default
        # Enables mocking in unit tests
        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            self.dynamodb = boto3.resource(
                "dynamodb",
                endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
                region_name=os.getenv("AWS_REGION", "eu-west-1"),
            )

        self.table = self.dynamodb.Table(self.table_name)

    def save_event(self, event_item: dict) -> dict:
        """
        Save sensor event to DynamoDB

        Args:
            event_item: Event dictionary to save

        Returns:
            Saved event dictionary

        Raises:
            ClientError: When DynamoDB operation fails
        """
        event_id = event_item.get("event_id", "unknown")
        try:
            logger.debug(f"Saving event: {event_id}")
            self.table.put_item(Item=event_item)
            logger.info(f"Event saved successfully: {event_id}")
            return event_item
        except ClientError as e:
            # DynamoDB-specific errors (throttling, capacity, etc.)
            error_code = e.response["Error"]["Code"]
            logger.error(f"DynamoDB error saving event {event_id}: {error_code} - {e}")
            raise
        except Exception as e:
            # Unexpected errors (serialization, network, etc.)
            logger.error(
                f"Unexpected error saving event {event_id}: {e}", exc_info=True
            )
            raise

    def get_events_by_room(
        self, room_id: str, limit: int = 50, start_time: Optional[datetime] = None
    ) -> List[dict]:
        """
        Get events for a specific room

        Args:
            room_id: Room identifier to query
            limit: Maximum number of events to return
            start_time: Optional start time filter

        Returns:
            List of event dictionaries

        Raises:
            ClientError: When DynamoDB operation fails
        """
        try:
            logger.debug(f"Fetching events for room: {room_id}, limit: {limit}")
            query_kwargs = {
                "KeyConditionExpression": Key("room_id").eq(room_id),
                "Limit": limit,
                "ScanIndexForward": False,  # Most recent first
            }

            if start_time:
                logger.debug(f"Filtering events from: {start_time.isoformat()}")
                query_kwargs["KeyConditionExpression"] &= Key("timestamp").gte(
                    start_time.isoformat()
                )

            response = self.table.query(**query_kwargs)
            items = response.get("Items", [])
            logger.info(f"Retrieved {len(items)} events for room {room_id}")
            return items
        except ClientError as e:
            # DynamoDB-specific errors (throttling, invalid query, etc.)
            error_code = e.response["Error"]["Code"]
            logger.error(
                f"DynamoDB error querying events for room {room_id}: {error_code} - {e}"
            )
            raise
        except Exception as e:
            # Unexpected errors
            logger.error(
                f"Unexpected error querying events for room {room_id}: {e}",
                exc_info=True,
            )
            raise

    def get_recent_events(self, limit: int = 100) -> List[dict]:
        """
        Get most recent events across all rooms

        Args:
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries sorted by timestamp

        Raises:
            ClientError: When DynamoDB operation fails

        Note:
            Uses scan() which is inefficient for large tables.
            Consider using query with GSI for production use.
        """
        try:
            logger.debug(f"Fetching recent events, limit: {limit}")
            response = self.table.scan(Limit=limit)
            items = response.get("Items", [])

            # Sort by timestamp descending
            items.sort(key=lambda x: x["timestamp"], reverse=True)
            event_count = len(items[:limit])
            logger.info(f"Retrieved {event_count} recent events")
            return items[:limit]
        except ClientError as e:
            # DynamoDB-specific errors (throttling, capacity exceeded)
            error_code = e.response["Error"]["Code"]
            logger.error(f"DynamoDB error scanning recent events: {error_code} - {e}")
            raise
        except Exception as e:
            # Unexpected errors (sorting, etc.)
            logger.error(f"Unexpected error fetching recent events: {e}", exc_info=True)
            raise
