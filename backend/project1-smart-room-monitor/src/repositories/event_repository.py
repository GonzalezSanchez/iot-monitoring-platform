"""
Event Repository
Handles DynamoDB operations for sensor events
"""
import os
from datetime import datetime
from typing import List, Optional
import boto3
from boto3.dynamodb.conditions import Key


class EventRepository:
    """Repository for sensor events in DynamoDB"""
    
    def __init__(self):
        self.table_name = os.getenv('DYNAMODB_TABLE_EVENTS', 'SensorEvents')
        self.dynamodb = boto3.resource(
            'dynamodb',
            endpoint_url=os.getenv('AWS_ENDPOINT_URL'),
            region_name=os.getenv('AWS_REGION', 'eu-west-1')
        )
        self.table = self.dynamodb.Table(self.table_name)
    
    def save_event(self, event_item: dict) -> dict:
        """Save sensor event to DynamoDB"""
        self.table.put_item(Item=event_item)
        return event_item
    
    def get_events_by_room(
        self,
        room_id: str,
        limit: int = 50,
        start_time: Optional[datetime] = None
    ) -> List[dict]:
        """Get events for a specific room"""
        query_kwargs = {
            'KeyConditionExpression': Key('room_id').eq(room_id),
            'Limit': limit,
            'ScanIndexForward': False  # Most recent first
        }
        
        if start_time:
            query_kwargs['KeyConditionExpression'] &= Key('timestamp').gte(
                start_time.isoformat()
            )
        
        response = self.table.query(**query_kwargs)
        return response.get('Items', [])
    
    def get_recent_events(self, limit: int = 100) -> List[dict]:
        """Get most recent events across all rooms"""
        response = self.table.scan(Limit=limit)
        items = response.get('Items', [])
        
        # Sort by timestamp descending
        items.sort(key=lambda x: x['timestamp'], reverse=True)
        return items[:limit]
