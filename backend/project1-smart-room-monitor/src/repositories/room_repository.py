"""
Room Repository
Handles DynamoDB operations for room status
"""
import logging
import os
from datetime import datetime
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError
from src.models.room import Room

# Configure logger
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
        # Allow table name override for testing or multi-environment use
        self.table_name = table_name or os.getenv('DYNAMODB_TABLE_ROOMS', 'RoomStatus')
        
        # Use injected resource or create default
        # Enables mocking in unit tests
        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            self.dynamodb = boto3.resource(
                'dynamodb',
                endpoint_url=os.getenv('AWS_ENDPOINT_URL'),
                region_name=os.getenv('AWS_REGION', 'eu-west-1')
            )
        
        self.table = self.dynamodb.Table(self.table_name)
    
    def save_room(self, room: Room) -> Room:
        """
        Save or update room status
        
        Args:
            room: Room object to save
            
        Returns:
            Room object
            
        Raises:
            ClientError: When DynamoDB operation fails
        """
        try:
            logger.debug(f"Saving room: {room.room_id}")
            self.table.put_item(Item=room.to_dynamodb_item())
            logger.info(f"Room saved successfully: {room.room_id}")
            return room
        except ClientError as e:
            # DynamoDB-specific errors (throttling, capacity, etc.)
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error saving room {room.room_id}: {error_code} - {e}")
            raise
        except Exception as e:
            # Unexpected errors (serialization, network, etc.)
            logger.error(f"Unexpected error saving room {room.room_id}: {e}", exc_info=True)
            raise
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """
        Get room by ID
        
        Args:
            room_id: Unique room identifier
            
        Returns:
            Room object if found, None otherwise
            
        Raises:
            ClientError: When DynamoDB operation fails
        """
        try:
            logger.debug(f"Fetching room: {room_id}")
            response = self.table.get_item(Key={'room_id': room_id})
            item = response.get('Item')
            
            if item:
                logger.debug(f"Room found: {room_id}")
                return Room.from_dynamodb_item(item)
            logger.debug(f"Room not found: {room_id}")
            return None
        except ClientError as e:
            # DynamoDB-specific errors
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error fetching room {room_id}: {error_code} - {e}")
            raise
        except Exception as e:
            # Unexpected errors (deserialization, etc.)
            logger.error(f"Unexpected error fetching room {room_id}: {e}", exc_info=True)
            raise
    
    def get_all_rooms(self) -> List[Room]:
        """
        Get all rooms with pagination support
        
        Returns:
            List of Room objects
            
        Raises:
            ClientError: When DynamoDB operation fails
            
        Note:
            Uses scan() with automatic pagination to handle tables > 1MB.
            DynamoDB returns max 1MB per scan operation.
        """
        try:
            logger.debug("Fetching all rooms with pagination")
            items = []
            
            # Initial scan
            response = self.table.scan()
            items.extend(response.get('Items', []))
            
            # Continue scanning if there are more results
            while 'LastEvaluatedKey' in response:
                logger.debug(f"Paginating scan, retrieved {len(items)} items so far")
                response = self.table.scan(
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items.extend(response.get('Items', []))
            
            room_count = len(items)
            logger.info(f"Retrieved {room_count} rooms from database")
            return [Room.from_dynamodb_item(item) for item in items]
        except ClientError as e:
            # DynamoDB-specific errors (throttling, capacity exceeded)
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error fetching all rooms: {error_code} - {e}")
            raise
        except Exception as e:
            # Unexpected errors (deserialization, etc.)
            logger.error(f"Unexpected error fetching all rooms: {e}", exc_info=True)
            raise
    
    def update_room_state(self, room_id: str, sensor_type: str, value: float) -> bool:
        """
        Update specific sensor value in room state
        
        Args:
            room_id: Room identifier
            sensor_type: Type of sensor (temperature, humidity, etc.)
            value: Sensor value to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug(f"Updating room state: {room_id}, {sensor_type}={value}")
            self.table.update_item(
                Key={'room_id': room_id},
                UpdateExpression=f'SET current_state.{sensor_type} = :val, last_update = :time',
                ExpressionAttributeValues={
                    ':val': value,
                    ':time': datetime.now().isoformat()
                }
            )
            logger.info(f"Room state updated: {room_id}")
            return True
        except ClientError as e:
            # DynamoDB-specific errors (item not found, conditional check failed, etc.)
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error updating room {room_id}: {error_code} - {e}")
            return False
        except Exception as e:
            # Unexpected errors
            logger.error(f"Unexpected error updating room state for {room_id}: {e}", exc_info=True)
            return False
