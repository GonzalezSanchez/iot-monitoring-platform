# Project 1: Smart Room Monitor

## Beschrijving

Real-time monitoring systeem voor conferentiezalen met IoT sensoren. Detecteert bezetting, temperatuur, luchtkwaliteit en energieverbruik.

## Tech Stack

- **Runtime:** Python 3.11
- **Cloud Services:** AWS Lambda, DynamoDB, API Gateway, CloudWatch
- **Containerization:** Docker
- **Testing:** pytest

## Features

- Real-time sensor data processing
- Anomaly detection (temperatuur, CO2)
- Historical data storage
- REST API voor data retrieval
- WebSocket support voor live updates

## API Endpoints

### POST /sensors/data
Ontvang sensor readings

**Request:**
```json
{
  "room_id": "conference-a1",
  "timestamp": "2026-01-07T10:30:00Z",
  "temperature": 22.5,
  "humidity": 45,
  "co2": 650,
  "occupancy": true
}
```

**Response:**
```json
{
  "status": "success",
  "data_id": "uuid-here"
}
```

### GET /sensors/data/{room_id}
Haal sensor data op voor een kamer

**Query Parameters:**
- `from`: Start timestamp (ISO 8601)
- `to`: End timestamp (ISO 8601)
- `limit`: Max aantal resultaten (default: 100)

**Response:**
```json
{
  "room_id": "conference-a1",
  "data": [
    {
      "timestamp": "2026-01-07T10:30:00Z",
      "temperature": 22.5,
      "humidity": 45,
      "co2": 650,
      "occupancy": true
    }
  ]
}
```

### GET /sensors/alerts/{room_id}
Haal actieve alerts op

## Database Schema (DynamoDB)

**Table:** sensor_readings

| Attribute | Type | Description |
|-----------|------|-------------|
| room_id (PK) | String | Kamer identificatie |
| timestamp (SK) | String | ISO 8601 timestamp |
| temperature | Number | Temperatuur in °C |
| humidity | Number | Luchtvochtigheid % |
| co2 | Number | CO2 ppm |
| occupancy | Boolean | Bezet ja/nee |

**Table:** alerts

| Attribute | Type | Description |
|-----------|------|-------------|
| alert_id (PK) | String | UUID |
| room_id | String | Kamer identificatie |
| alert_type | String | temperature/co2/humidity |
| severity | String | warning/critical |
| timestamp | String | ISO 8601 timestamp |
| resolved | Boolean | Opgelost ja/nee |

## Architectuur

```
API Gateway → Lambda (Ingest) → DynamoDB (sensor_readings)
                               ↓
                         Lambda (Analyzer) → DynamoDB (alerts)
                                            ↓
                                      CloudWatch Alarms
```

## Installatie & Gebruik

```bash
cd backend/project1-smart-room-monitor

# Build Docker image
docker build -t smart-room-monitor .

# Run lokaal
docker run -p 8000:8000 smart-room-monitor

# Deploy naar AWS
./deploy.sh
```

## Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Coverage report
pytest --cov=src tests/
```
