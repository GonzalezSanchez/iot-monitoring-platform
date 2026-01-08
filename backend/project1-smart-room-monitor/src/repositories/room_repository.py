"""
Room Repository
Handles DynamoDB operations for room status
"""
import os
from datetime import datetime
from typing import List, Optional
import boto3
from src.models.room import Room


class RoomRepository:
    """Repository for room status in DynamoDB"""
    
    def __init__(self):
        self.table_name = os.getenv('DYNAMODB_TABLE_ROOMS', 'RoomStatus')
        self.dynamodb = boto3.resource(
            'dynamodb',
            endpoint_url=os.getenv('AWS_ENDPOINT_URL'),
            region_name=os.getenv('AWS_REGION', 'eu-west-1')
        )
        self.table = self.dynamodb.Table(self.table_name)
    
    def save_room(self, room: Room) -> Room:
        """Save or update room status"""
        self.table.put_item(Item=room.to_dynamodb_item())
        return room
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """Get room by ID"""
        response = self.table.get_item(Key={'room_id': room_id})
        item = response.get('Item')
        
        if item:
            return Room.from_dynamodb_item(item)
        return None
    
    def get_all_rooms(self) -> List[Room]:
        """Get all rooms"""
        response = self.table.scan()
        items = response.get('Items', [])
        
        return [Room.from_dynamodb_item(item) for item in items]
    
    def update_room_state(self, room_id: str, sensor_type: str, value: float) -> bool:
        """Update specific sensor value in room state"""
        try:
            self.table.update_item(
                Key={'room_id': room_id},
                UpdateExpression=f'SET current_state.{sensor_type} = :val, last_update = :time',
                ExpressionAttributeValues={
                    ':val': value,
                    ':time': datetime.now().isoformat()
                }
            )
            return True
        except Exception:
            return False
