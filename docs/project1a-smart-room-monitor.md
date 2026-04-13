# Project 1a — Smart Room Monitor (AWS Lambda)

## Beschrijving

Real-time monitoring systeem voor conferentiezalen met IoT sensoren. Detecteert bezetting, temperatuur, luchtkwaliteit en beweging via individuele sensor events. Verwerkt events door anomaly detection en houdt room state bij in real time.

## Tech Stack

- **Runtime:** Python 3.12
- **Cloud Services:** AWS Lambda, DynamoDB, API Gateway (HTTP API), CloudWatch
- **Containerization:** Docker (lokale ontwikkeling)
- **Testing:** pytest + moto
- **CI/CD:** GitHub Actions
- **IaC:** CloudFormation

## CI/CD & Infrastructure as Code

- Deployment gebeurt automatisch via GitHub Actions (`.github/workflows/deploy.yml`).
- CloudFormation-template (`infrastructure/cloudformation.yaml`) definieert alle AWS resources (Lambda functions, API Gateway, IAM role, Lambda permissions).
- DynamoDB tabellen worden apart beheerd via een gedeelde CloudFormation stack.
- Testen worden automatisch uitgevoerd vóór deployment.

## Features

- Real-time sensor event ingestion (temperature, humidity, occupancy, motion)
- Anomaly detection met drempelwaarden per sensor type (`normal` / `warning` / `alert`)
- Room state tracking — elke kamer heeft een geaggregeerde status op basis van de laatste sensor readings
- REST API voor event ingestion en room queries
- Volledige CI/CD pipeline en automatische infrastructuur provisioning via CloudFormation

## API Endpoints

### POST /events
Stuur een sensor event in.

**Request:**
```json
{
  "room_id": "conference-a1",
  "sensor_type": "temperature",
  "value": 22.5,
  "timestamp": "2026-01-13T10:30:00Z"
}
```

`sensor_type` is één van: `temperature`, `humidity`, `occupancy`, `motion`

**Response (201):**
```json
{
  "message": "Event ingested successfully",
  "event_id": "01JFKZ...",
  "room_id": "conference-a1",
  "sensor_type": "temperature",
  "value": 22.5,
  "unit": "°C",
  "timestamp": "2026-01-13T10:30:00Z",
  "status": "normal"
}
```

`status` is één van: `normal`, `warning`, `alert` — ingesteld door anomaly detection.

---

### GET /rooms
Haal een lijst op van alle kamers met hun huidige state.

**Response (200):**
```json
{
  "rooms": [
    {
      "room_id": "conference-a1",
      "name": "Conference Room A1",
      "status": "active",
      "last_update": "2026-01-13T10:30:00Z",
      "current_state": {
        "temperature": 22.5,
        "humidity": 45.0,
        "occupancy": 3,
        "motion": true
      },
      "alert_count_24h": 0
    }
  ],
  "count": 1
}
```

`status` is één van: `active`, `warning`, `alert`, `offline`

---

### GET /rooms/{room_id}
Haal details op voor één kamer, inclusief de 50 meest recente events.

**Response (200):**
```json
{
  "room": { ... },
  "recent_events": [ ... ],
  "event_count": 50
}
```

## Database Schema (DynamoDB)

**Table:** `prod-SensorEvents`

| Attribute | Type | Description |
|-----------|------|-------------|
| room_id (PK) | String | Kamer identificatie |
| timestamp (SK) | String | ISO 8601 timestamp |
| event_id | String | ULID — uniek event ID |
| sensor_type | String | `temperature` \| `humidity` \| `occupancy` \| `motion` |
| value | Number | Sensorwaarde |
| unit | String | Eenheid (`°C`, `%`, `people`, `boolean`) |
| status | String | `normal` \| `warning` \| `alert` |

**Table:** `prod-RoomStatus`

| Attribute | Type | Description |
|-----------|------|-------------|
| room_id (PK) | String | Kamer identificatie |
| name | String | Weergavenaam |
| status | String | `active` \| `warning` \| `alert` \| `offline` |
| last_update | String | ISO 8601 timestamp van laatste event |
| current_state | Map | Laatste waarden per sensor type |
| alert_count_24h | Number | Aantal alerts in de laatste 24 uur |

## Architectuur

```
API Client
    │
    ▼
API Gateway (HTTP API)
    │
    ├── POST /events  ──► Lambda (IngestEvent)
    │                         │
    │                         ├── AnomalyDetector (threshold checks)
    │                         ├── EventRepository  → DynamoDB (SensorEvents)
    │                         └── RoomRepository   → DynamoDB (RoomStatus)
    │
    ├── GET /rooms    ──► Lambda (GetRooms)
    │                         └── RoomRepository   → DynamoDB (RoomStatus)
    │
    └── GET /rooms/{id} ──► Lambda (GetRoomDetail)
                              ├── RoomRepository   → DynamoDB (RoomStatus)
                              └── EventRepository  → DynamoDB (SensorEvents)
```

## Security

Authentication is intentionally excluded from this project. The API endpoints are public to keep the demo accessible without token management.

For a security-focused implementation with device authentication (API keys, JWT via AWS Cognito) and rate limiting, see [Project 3: IoT Device Gateway](project3-iot-gateway.md).

## Installatie & Gebruik

```bash
cd backend/project1a-smart-room-monitor

# Installeer dependencies
pip install -r requirements.txt

# Lokaal testen
docker-compose -f docker/docker-compose.yml up

# Deploy naar AWS (via GitHub Actions of handmatig)
aws cloudformation deploy \
  --template-file infrastructure/cloudformation.yaml \
  --stack-name prod-smart-room-monitor \
  --capabilities CAPABILITY_NAMED_IAM
```

## Testing

```bash
# Unit tests
pytest tests/unit/

# Coverage report
pytest --cov=src tests/
```
