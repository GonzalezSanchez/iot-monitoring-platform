# Project 1b — Smart Room Monitor (FastAPI)

## Overzicht

FastAPI-versie van de Smart Room Monitor backend. Dezelfde domeinlogica als project 1a (models, repositories, services), maar ingezet als containerized applicatie met FastAPI in plaats van AWS Lambda.

## Inhoud

- Doel en scope
- Architectuuroverzicht
- Verschillen t.o.v. Lambda-versie
- API-endpoints
- Database schema
- Hergebruikte code
- Installatie en starten
- Security

## 1. Doel en scope

Deze backend biedt een REST API voor het monitoren van ruimtes en sensorgegevens, als alternatief voor de serverless Lambda-oplossing uit project 1a. Het demonstreert dat dezelfde businesslogica infrastructuuronafhankelijk is.

**Live:** [iot.gonzalezsanchez.dev](https://iot.gonzalezsanchez.dev)
**API docs:** [iot.gonzalezsanchez.dev/docs](https://iot.gonzalezsanchez.dev/docs)

## 2. Architectuuroverzicht

```
API Client
    │
    ▼
FastAPI (uvicorn)
    │
    ├── POST /events        → EventService → AnomalyDetector
    │                                      → EventRepository → DynamoDB
    │                                      → RoomRepository  → DynamoDB
    │
    ├── GET  /events        → EventRepository → DynamoDB
    ├── GET  /rooms         → RoomRepository  → DynamoDB
    ├── GET  /rooms/{id}    → RoomRepository  → DynamoDB
    ├── GET  /rooms/{id}/events → EventRepository → DynamoDB
    └── GET  /health        → { "status": "ok" }
```

- **Framework:** FastAPI + uvicorn
- **Database:** DynamoDB (AWS) via boto3
- **Structuur:** `models/`, `repositories/`, `services/`, `src/main.py`
- **Deployment:** Docker + nginx + Cloudflare tunnel

## 3. Verschillen t.o.v. Lambda-versie (project 1a)

| Aspect | Project 1a (Lambda) | Project 1b (FastAPI) |
|--------|--------------------|--------------------|
| Runtime | AWS Lambda (per-request) | Containerized server (altijd aan) |
| Routing | API Gateway routes → aparte Lambda per endpoint | FastAPI router in één applicatie |
| Lokaal testen | Moto mocks + Docker | Echte DynamoDB Local of AWS |
| Schaling | Automatisch (serverless) | Zelf verantwoordelijk |
| Kosten | Pay-per-request | Vaste serverkosten |

## 4. API-endpoints

### GET /health
Geeft de health status van de API terug.

**Response (200):**
```json
{ "status": "ok", "service": "smart-room-monitor" }
```

---

### POST /events
Ingesteer een sensor event. Doorloopt de volledige pipeline: anomaly detection → opslaan in DynamoDB → room state updaten.

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

**Response (201):** het verwerkte `SensorEvent` object inclusief `event_id`, `unit`, en `status`.

---

### GET /events
Haal sensor events op. Optioneel te filteren op kamer.

**Query parameters:**
- `room_id` (optioneel) — filtert op kamer; zonder filter worden alle events teruggegeven (table scan — alleen voor demo/kleine datasets)

**Response (200):** lijst van `SensorEvent` objecten.

---

### GET /rooms
Haal alle kamers op met hun huidige sensor state.

**Response (200):** lijst van `Room` objecten.

---

### GET /rooms/{room_id}
Haal de huidige state van één kamer op.

**Response (200):** `Room` object.
**Response (404):** `{ "detail": "Room not found" }`

---

### GET /rooms/{room_id}/events
Haal alle sensor events op voor één kamer, gesorteerd op timestamp (oplopend).

**Response (200):** lijst van `SensorEvent` objecten.
**Response (404):** `{ "detail": "Room not found" }`

## 5. Database Schema (DynamoDB)

Identiek aan project 1a — gedeelde DynamoDB tabellen.

**Table:** `prod-SensorEvents`

| Attribute | Type | Description |
|-----------|------|-------------|
| room_id (PK) | String | Kamer identificatie |
| timestamp (SK) | String | ISO 8601 timestamp |
| event_id | String | ULID |
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
| last_update | String | ISO 8601 timestamp |
| current_state | Map | Laatste waarden per sensor type |
| alert_count_24h | Number | Aantal alerts in de laatste 24 uur |

## 6. Hergebruikte code

- `models/`, `repositories/`, `services/` zijn grotendeels overgenomen uit project 1a
- Aanpassingen voor FastAPI: Pydantic v2 response models, dependency injection via module-level instantiatie
- `src/main.py` vervangt de afzonderlijke Lambda handlers

## 7. Installatie en starten

```bash
cd backend/project1b-smart-room-monitor-fastapi

# Lokaal (met DynamoDB Local via Docker)
docker-compose -f docker/docker-compose.yml up

# Of direct met uvicorn (vereist AWS credentials of .env)
cp .env.example .env  # vul AWS credentials in
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## 8. Security

Authentication is intentionally excluded from this project. The API endpoints are public to keep the demo accessible without token management.

For a security-focused implementation with device authentication (API keys, JWT via AWS Cognito) and rate limiting, see [Project 3: IoT Device Gateway](project3-iot-gateway.md).

## 9. Testing

```bash
# Unit + integration tests
pytest tests/

# Coverage
pytest --cov=src tests/
```
