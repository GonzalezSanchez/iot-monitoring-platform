# Smart Room Monitor — AWS Lambda (Project 1a)

Real-time IoT sensor monitoring API for conference rooms, built with AWS Lambda and API Gateway.

This is the serverless counterpart to [Project 1b](../project1b-smart-room-monitor-fastapi/) (FastAPI + Docker). Same domain logic and clean architecture, different infrastructure layer.

**Status:** Tested with AWS (Lambda, DynamoDB, API Gateway, CloudWatch)

---

## Tech Stack

- **Python 3.11** — Pydantic v2, boto3
- **AWS:** Lambda, API Gateway, DynamoDB, CloudWatch
- **LocalStack** — full AWS simulation for local development
- **pytest + moto** — unit tests with mocked DynamoDB (80%+ coverage)
- **mypy + ruff** — static type checking and linting

---

## Architecture

```
POST /events
    └── EventService.process_event()
            ├── AnomalyDetector   → sets status: normal / warning / alert
            ├── EventRepository   → persists event to DynamoDB (SensorEvents table)
            └── RoomRepository    → upserts room state (RoomStatus table)
```

Clean layered architecture:

```
handlers/       Lambda entry points (API Gateway events)
    └── services/       application logic, anomaly detection
        └── repositories/   DynamoDB access
            └── models/     Pydantic domain models
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/events` | Ingest a sensor event — runs anomaly detection |
| GET | `/rooms` | List all rooms with current state |
| GET | `/rooms/{room_id}` | Get current state of a specific room |

### Sensor Types

`temperature`, `humidity`, `occupancy`, `motion`

### Anomaly Detection Thresholds

| Sensor | Warning | Alert |
|--------|---------|-------|
| Temperature | > 26°C or < 18°C | >= 30°C or <= 10°C |
| Humidity | > 70% or < 30% | >= 80% or <= 20% |
| Occupancy | > 20 people | >= 30 people |

---

## Local Setup

### Prerequisites

- Python 3.11+
- Docker

### 1. Start LocalStack

```bash
docker-compose -f docker/docker-compose.yml up -d
```

LocalStack will be available at `http://localhost:4566` and auto-creates DynamoDB tables on startup.

### 2. Install dependencies and run tests

```bash
pip install -r requirements-dev.txt
pytest tests/ --cov=src
```

### 3. Simulate sensors (optional)

```bash
python scripts/sensor_simulator.py --api-url http://localhost:8080
```

---

## Running Tests

Tests use `moto` to mock DynamoDB — no Docker or AWS needed.

```bash
pytest tests/ -v
```

Coverage: 80%+ across all source modules.

---

## Project Structure

```
project1a-smart-room-monitor/
├── src/
│   ├── handlers/          # Lambda entry points
│   ├── models/            # Pydantic domain models
│   ├── repositories/      # DynamoDB access layer
│   ├── services/          # Business logic + anomaly detection
│   └── utils/             # HTTP response helpers
├── tests/
│   └── unit/              # pytest + moto tests
├── infrastructure/
│   ├── cloudformation.yaml         # Lambda + API Gateway + DynamoDB + IAM
│   └── github-actions-iam.yml      # CI/CD IAM user (least-privilege)
├── docker/
│   ├── docker-compose.yml          # LocalStack
│   ├── Dockerfile                  # Lambda runtime image
│   └── localstack-init.sh          # Auto-creates tables on startup
└── scripts/
    ├── add_test_room.py            # Seed demo room data
    └── sensor_simulator.py         # Simulate IoT sensor events
```

---

## Deployment

Deploy to AWS using CloudFormation:

```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation.yaml \
  --stack-name smart-room-monitor-prod \
  --capabilities CAPABILITY_IAM
```

---

© 2026 Álvaro González Sánchez
