# Smart Room Monitor — FastAPI (Project 1b)

Real-time IoT sensor monitoring API for conference rooms, built with FastAPI and DynamoDB.

This is the locally-runnable counterpart to [Project 1](../project1a-smart-room-monitor/) (AWS Lambda). Same domain logic and clean architecture, different infrastructure layer — no AWS account needed.

**Status:** Fully implemented and tested (12/12 tests passing)

---

## Tech Stack

- **Python 3.12** — FastAPI, Pydantic v2, boto3
- **DynamoDB Local** — via Docker (no AWS account required)
- **pytest + moto** — unit and integration tests with mocked DynamoDB
- **mypy + pre-commit** — static type checking enforced on every commit

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
main.py (FastAPI routes)
    └── services/       application logic, anomaly detection
        └── repositories/   DynamoDB access
            └── models/     Pydantic domain models
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/events` | List all events (optional `?room_id=` filter) |
| POST | `/events` | Ingest a sensor event — runs anomaly detection |
| GET | `/rooms` | List all rooms with current state |
| GET | `/rooms/{room_id}` | Get current state of a specific room |
| GET | `/rooms/{room_id}/events` | Get all events for a specific room |

Interactive docs available at `http://localhost:8000/docs` when running locally.

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

### 1. Start DynamoDB Local

```bash
cd docker
docker-compose up -d
```

DynamoDB will be available at `http://localhost:8001`.

### 2. Create tables

```bash
python scripts/create_roomstatus_table_local.py
```

### 3. Install dependencies and run

```bash
pip install -r requirements-dev.txt
uvicorn main:app --reload
```

API available at `http://localhost:8000`.

### 4. Add test data (optional)

```bash
python scripts/add_test_room_local.py
```

---

## Running Tests

Tests use `moto` to mock DynamoDB — no Docker or AWS needed.

```bash
pytest tests/ -v
```

All 12 tests cover: health check, event ingestion, anomaly detection thresholds, input validation, room auto-creation, and the room events endpoint.

**Coverage: 91%** across all source modules (100% on models and repositories).

---

## Project Structure

```
project1b-smart-room-monitor-fastapi/
├── main.py                  # FastAPI app, routes
├── models/
│   ├── sensor_event.py      # SensorEvent (Pydantic v2)
│   └── room.py              # Room, RoomState (Pydantic v2)
├── repositories/
│   ├── event_repository.py  # DynamoDB: SensorEvents table
│   └── room_repository.py   # DynamoDB: RoomStatus table
├── services/
│   ├── event_service.py     # Orchestrates event processing
│   └── anomaly_detector.py  # Threshold-based anomaly logic
├── tests/
│   ├── conftest.py          # moto fixtures, dependency injection
│   └── test_endpoints.py    # 12 endpoint tests
├── docker/
│   └── docker-compose.yml   # DynamoDB Local
└── scripts/
    ├── create_roomstatus_table_local.py
    └── add_test_room_local.py
```

---

## Production Deployment

The project is deployed at **https://iot.gonzalezsanchez.dev** using Docker Compose on a self-hosted server behind a Cloudflare tunnel.

### Stack

```
Cloudflare tunnel
    └── nginx (port 3000)
            ├── /* → React SPA (static files)
            └── /rooms, /events, /health, /docs → FastAPI backend (port 8000)
```

### Infrastructure (AWS)

Provisioned via CloudFormation (`infrastructure/dynamodb-iam.yml`):
- `prod-RoomStatus` — DynamoDB table, PAY_PER_REQUEST
- `prod-SensorEvents` — DynamoDB table, PAY_PER_REQUEST
- `iot-monitoring-app` — IAM user with least-privilege policy (GetItem, PutItem, Query, Scan only)

### Running in production

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Requires `.env.prod` in `backend/project1b-smart-room-monitor-fastapi/` with AWS credentials (not committed to git).

### Scaling to Kubernetes

This deployment uses Docker Compose, which is the right tool for a single-server setup. The architecture is intentionally simple — 2 services, no orchestration overhead.

If the platform were to scale (multiple backend replicas, high availability, multi-region), the natural next step would be Kubernetes (e.g. AWS EKS). Each service maps directly to a Kubernetes `Deployment`, the nginx ingress would be replaced by an Ingress controller, and DynamoDB already scales seamlessly on the AWS side. The clean separation between services makes this migration straightforward.

---

## Example Request

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": "room-1",
    "sensor_type": "temperature",
    "value": 32.0,
    "timestamp": "2026-01-15T12:00:00"
  }'
```

Response:

```json
{
  "room_id": "room-1",
  "sensor_type": "temperature",
  "value": 32.0,
  "unit": "°C",
  "timestamp": "2026-01-15T12:00:00",
  "status": "alert"
}
```

---

© 2026 Álvaro González Sánchez
