import os

from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
TOPIC_SENSOR_EVENTS = os.getenv("TOPIC_SENSOR_EVENTS", "sensor-events")
TOPIC_DLQ = os.getenv("TOPIC_DLQ", "sensor-events.dlq")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "gateway-normalizer")

# Shared-contract tables owned by project 1b (docs/project3b-iot-gateway.md)
SENSOR_EVENTS_TABLE = os.getenv("SENSOR_EVENTS_TABLE", "prod-SensorEvents")
ROOM_STATUS_TABLE = os.getenv("ROOM_STATUS_TABLE", "prod-RoomStatus")
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
