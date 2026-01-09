"""
Get Room Detail Lambda Handler
GET /rooms/{id} - Returns detailed room information with recent events
"""
import logging
from typing import Dict, Any
from repositories.room_repository import RoomRepository
from repositories.event_repository import EventRepository
from utils.response import success_response, error_response

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize repositories once for Lambda warm starts
room_repository = RoomRepository()
event_repository = EventRepository()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for retrieving room details with recent events

    Args:
        event: Lambda event object containing API Gateway request
        context: Lambda context object

    Returns:
        API Gateway response dict with statusCode and body
    """
    logger.info("Processing get room detail request")

    try:
        # Extract room_id from path parameters
        path_params = event.get("pathParameters", {})
        room_id = path_params.get("id")

        if not room_id:
            logger.warning("Missing room_id in path parameters")
            return error_response("Room ID is required", 400)

        # Get room from repository
        room = room_repository.get_room(room_id)

        if not room:
            logger.warning(f"Room not found: {room_id}")
            return error_response(f"Room not found: {room_id}", 404)

        # Get recent events for this room
        recent_events = event_repository.get_events_by_room(room_id=room_id, limit=50)

        logger.info(f"Retrieved room {room_id} with {len(recent_events)} recent events")

        return success_response(
            data={
                "room": room.model_dump(),
                "recent_events": recent_events,
                "event_count": len(recent_events),
            },
            status_code=200,
        )

    except Exception as e:
        # Repository or unexpected errors
        logger.error(f"Error retrieving room detail: {e}", exc_info=True)
        return error_response("Failed to retrieve room detail", 500)
