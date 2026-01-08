"""
Ingest Event Lambda Handler
POST /events - Receives and processes sensor events
"""
import json
import logging
from typing import Dict, Any
from src.services.event_service import EventService, EventServiceError
from src.utils.response import success_response, error_response

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize EventService once for Lambda warm starts
event_service = EventService()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for ingesting sensor events
    
    Args:
        event: Lambda event object containing API Gateway request
        context: Lambda context object
        
    Returns:
        API Gateway response dict with statusCode and body
    """
    logger.info("Processing ingest event request")
    
    try:
        # Parse request body
        body = event.get('body')
        if not body:
            logger.warning("Empty request body received")
            return error_response("Request body is required", 400)
        
        # Parse JSON body
        try:
            event_data = json.loads(body) if isinstance(body, str) else body
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request body: {e}")
            return error_response("Invalid JSON format", 400)
        
        # Validate required fields
        required_fields = ['room_id', 'sensor_type', 'value', 'timestamp']
        missing_fields = [field for field in required_fields if field not in event_data]
        
        if missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}")
            return error_response(
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )
        
        # Process event through EventService
        result = event_service.process_event(event_data)
        
        logger.info(f"Event processed successfully: {result.get('event_id')}")
        
        return success_response(
            data={
                "message": "Event ingested successfully",
                **result
            },
            status_code=201
        )
        
    except EventServiceError as e:
        # Business logic errors (validation, database errors)
        logger.error(f"EventService error: {e}")
        return error_response(str(e), 422)
    
    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error in ingest_event handler: {e}", exc_info=True)
        return error_response("Internal server error", 500)
