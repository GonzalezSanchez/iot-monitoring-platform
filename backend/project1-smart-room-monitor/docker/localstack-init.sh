#!/bin/bash

# LocalStack initialization script for DynamoDB tables
# This script runs automatically when LocalStack starts

echo "Starting LocalStack initialization..."

# Wait for LocalStack to be fully ready
sleep 5

# AWS configuration for LocalStack
export AWS_DEFAULT_REGION=eu-west-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
ENDPOINT="http://localhost:4566"

echo "Creating DynamoDB tables..."

# Create rooms table
awslocal dynamodb create-table \
    --table-name rooms \
    --attribute-definitions \
        AttributeName=room_id,AttributeType=S \
    --key-schema \
        AttributeName=room_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region eu-west-1 \
    || echo "Table 'rooms' may already exist"

# Create sensor_events table with GSI
awslocal dynamodb create-table \
    --table-name sensor_events \
    --attribute-definitions \
        AttributeName=event_id,AttributeType=S \
        AttributeName=room_id,AttributeType=S \
        AttributeName=timestamp,AttributeType=S \
    --key-schema \
        AttributeName=event_id,KeyType=HASH \
    --global-secondary-indexes \
        "[{
            \"IndexName\": \"RoomTimestampIndex\",
            \"KeySchema\": [
                {\"AttributeName\":\"room_id\",\"KeyType\":\"HASH\"},
                {\"AttributeName\":\"timestamp\",\"KeyType\":\"RANGE\"}
            ],
            \"Projection\": {\"ProjectionType\":\"ALL\"},
            \"ProvisionedThroughput\": {
                \"ReadCapacityUnits\": 5,
                \"WriteCapacityUnits\": 5
            }
        }]" \
    --billing-mode PROVISIONED \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region eu-west-1 \
    || echo "Table 'sensor_events' may already exist"

echo "Waiting for tables to be active..."
sleep 3

# Verify tables were created
echo "Listing DynamoDB tables:"
awslocal dynamodb list-tables --region eu-west-1

# Insert sample data for testing
echo "Inserting sample room data..."
awslocal dynamodb put-item \
    --table-name rooms \
    --item '{
        "room_id": {"S": "room-001"},
        "name": {"S": "Conference Room A"},
        "floor": {"N": "1"},
        "capacity": {"N": "12"},
        "current_temperature": {"N": "22.5"},
        "current_humidity": {"N": "45.0"},
        "current_occupancy": {"N": "0"},
        "last_updated": {"S": "2026-01-09T12:00:00Z"}
    }' \
    --region eu-west-1 \
    || echo "Sample data insertion failed"

awslocal dynamodb put-item \
    --table-name rooms \
    --item '{
        "room_id": {"S": "room-002"},
        "name": {"S": "Office 201"},
        "floor": {"N": "2"},
        "capacity": {"N": "4"},
        "current_temperature": {"N": "21.0"},
        "current_humidity": {"N": "50.0"},
        "current_occupancy": {"N": "2"},
        "last_updated": {"S": "2026-01-09T12:00:00Z"}
    }' \
    --region eu-west-1 \
    || echo "Sample data insertion failed"

echo "LocalStack initialization completed successfully!"
