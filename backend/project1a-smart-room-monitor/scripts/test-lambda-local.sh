#!/bin/bash
# Test Lambda handler directly in the iot-lambda container
# Usage: ./scripts/test-lambda-local.sh [handler_name] [event_file]

set -e

HANDLER=${1:-"handlers.get_rooms.lambda_handler"}
EVENT_FILE=${2:-"scripts/test-events/get-rooms-event.json"}

echo "🧪 Testing Lambda handler: $HANDLER"
echo "📄 Using event: $EVENT_FILE"
echo ""

# Execute Lambda handler in the container
docker exec -it iot-lambda python3 -c "
import json
import sys
import importlib

# Load test event
with open('/var/task/$EVENT_FILE', 'r') as f:
    event = json.load(f)

# Import and execute handler
module_path, function_name = '$HANDLER'.rsplit('.', 1)
module = importlib.import_module(module_path)
handler = getattr(module, function_name)

# Execute with mock context
class Context:
    def __init__(self):
        self.function_name = 'test-function'
        self.memory_limit_in_mb = 128
        self.invoked_function_arn = 'arn:aws:lambda:local:000000000000:function:test'
        self.aws_request_id = 'test-request-id'

result = handler(event, Context())
print(json.dumps(result, indent=2))
"

echo ""
echo "✅ Test completed"
