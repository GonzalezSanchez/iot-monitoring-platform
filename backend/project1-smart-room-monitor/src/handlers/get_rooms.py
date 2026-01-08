"""
Get Rooms Lambda Handler
GET /rooms - Returns list of all rooms with their current status
"""
import logging
from typing import Dict, Any
from src.repositories.room_repository import RoomRepository
from src.utils.response import success_response, error_response

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize RoomRepository once for Lambda warm starts
room_repository = RoomRepository()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for retrieving all rooms
    
    Args:
        event: Lambda event object containing API Gateway request
        context: Lambda context object
        
    Returns:
        API Gateway response dict with statusCode and body
    """
    logger.info("Processing get rooms request")
    
    try:
        # Get all rooms from repository
        rooms = room_repository.get_all_rooms()
        
        logger.info(f"Retrieved {len(rooms)} rooms")
        
        return success_response(
            data={
                "rooms": [room.model_dump() for room in rooms],
                "count": len(rooms)
            },
            status_code=200
        )
        
    except Exception as e:
        # Repository or unexpected errors
        logger.error(f"Error retrieving rooms: {e}", exc_info=True)
        return error_response("Failed to retrieve rooms", 500)
