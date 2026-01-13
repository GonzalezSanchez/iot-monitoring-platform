# Smart Room Monitor

Real-time IoT monitoring system for conference rooms using AWS serverless architecture.

## 🎯 Overview

This project demonstrates:
- ✅ Python OOP with clean architecture
- ✅ AWS Lambda + API Gateway + DynamoDB
- ✅ Docker containerization
- ✅ Unit testing with pytest (80%+ coverage)
- ✅ IoT sensor simulation

## 🏗️ Architecture

```
IoT Sensors → API Gateway → Lambda Handlers → DynamoDB
                                ↓
                          Anomaly Detection
                                ↓
                          Room State Update
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- AWS CLI (for deployment)

### Local Development

1. **Clone repository**
```bash
git clone <repo-url>
cd backend/project1-smart-room-monitor
```

2. **Start LocalStack**
```bash
docker-compose -f docker/docker-compose.yml up -d
```

3. **Run tests**
```bash
pip install -r requirements-dev.txt
pytest tests/ --cov=src
```

4. **Simulate sensors**
```bash
python scripts/sensor_simulator.py --duration 300
```

## 📡 API Endpoints

### POST /events
Ingest sensor event
```bash
curl -X POST http://localhost:8080/events \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": "room-a",
    "sensor_type": "temperature",
    "value": 22.5,
    "timestamp": "2026-01-07T12:00:00Z"
  }'
```

### GET /rooms
Get all rooms
```bash
curl http://localhost:8080/rooms
```

### GET /rooms/{room_id}
Get room details
```bash
curl http://localhost:8080/rooms/room-a
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_services.py -v
```

## 🎨 Project Structure

```
src/
├── handlers/          # Lambda handlers
├── models/            # Data models
├── repositories/      # Data access layer
├── services/          # Business logic
└── utils/             # Utilities

tests/
├── unit/              # Unit tests
├── integration/       # Integration tests
└── fixtures/          # Test data
```

## 📊 Database Schema

**SensorEvents Table (DynamoDB)**
- PK: room_id
- SK: timestamp
- Attributes: event_id, sensor_type, value, unit, status

**RoomStatus Table (DynamoDB)**
- PK: room_id
- Attributes: name, status, last_update, current_state, alert_count_24h

## 🔧 Configuration

Environment variables (see `.env.example`):
```
AWS_REGION=eu-west-1
DYNAMODB_TABLE_EVENTS=SensorEvents
DYNAMODB_TABLE_ROOMS=RoomStatus
```

## 🛳️ Deployment

Deploy to AWS using CloudFormation:
```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation.yaml \
  --stack-name smart-room-monitor \
  --capabilities CAPABILITY_IAM
```


## 🔒 Licentie

Deze code is uitsluitend bedoeld voor gebruik door het projectteam Smart Room Monitor. Gebruik, verspreiding of kopiëren door derden is niet toegestaan zonder expliciete toestemming.

## 🔒 Git & Deployment Best Practices

- Commit en push alleen broncode, scripts en configuratiebestanden.
- Voeg alle Lambda zip-bestanden (zoals lambda_package.zip, lambda_room_detail.zip, lambda_ingest_event.zip) toe aan .gitignore. Deze build-artifacts horen niet in git.
- Voeg testdata en coverage output (zoals htmlcov/, scripts/test-events/*.json) ook toe aan .gitignore.
- Herhaal dit voor elke nieuwe Lambda-functie (zoals room details, ingest event, etc).
- Frontend-bestanden en build-artifacts van de backend mogen niet naar elkaar gekopieerd of gecommit worden.

Zie .gitignore voor voorbeelden.
