# Project 3: IoT Device Gateway Simulator

## Beschrijving

Secure gateway voor IoT devices met authenticatie, rate limiting, en message queuing. Simuleert een production-ready IoT platform met device management.

## Implementatievarianten

Net als project 1/1b en 2a/2b wordt project 3 in twee varianten gebouwd — zelfde beveiligingsconcept, andere infrastructuur:

| | AWS variant (3a) | FastAPI variant (3b) |
|---|---|---|
| Device auth | Cognito + API Gateway authorizer | Custom API keys — gehashed in DynamoDB, gevalideerd via FastAPI `Depends()` |
| JWT | Cognito uitreikt | `python-jose` — zelf implementeren |
| Message queue | SQS | Lokaal: Redis of simpele DB queue |
| Rate limiting | API Gateway built-in | Custom middleware in FastAPI |

**Gekozen aanpak voor 3b:** optie 1 — API keys per device. Device registreert, ontvangt een gegenereerde key, elke request valideert via `Depends()`. Toont security thinking (hashing, least-privilege, rate limiting) zonder een volledige auth server. Past bij de portfolio filosofie: niet overengineeren, maar het principe aantonen.

---

## Tech Stack

- **Runtime:** Python 3.12
- **Cloud Services:** AWS API Gateway, Lambda, Cognito, DynamoDB, SQS
- **Containerization:** Docker
- **Testing:** pytest

## Features

- Device registration en authenticatie (JWT)
- Rate limiting per device
- Message queuing voor reliable delivery
- Device status monitoring
- Command & control interface
- Security: input validation, encryption

## API Endpoints

### POST /devices/register
Registreer een nieuw IoT device

**Request:**
```json
{
  "device_id": "sensor-001",
  "device_type": "temperature_sensor",
  "metadata": {
    "location": "conference-a1",
    "model": "DHT22"
  }
}
```

**Response:**
```json
{
  "device_id": "sensor-001",
  "api_key": "generated-api-key",
  "status": "registered"
}
```

### POST /devices/{device_id}/authenticate
Authenticeer en ontvang JWT token

**Request:**
```json
{
  "api_key": "generated-api-key"
}
```

**Response:**
```json
{
  "access_token": "jwt-token-here",
  "expires_in": 3600
}
```

### POST /messages
Verstuur bericht van device naar cloud

**Headers:**
```
Authorization: Bearer jwt-token-here
```

**Request:**
```json
{
  "device_id": "sensor-001",
  "payload": {
    "temperature": 22.5,
    "humidity": 45
  },
  "timestamp": "2026-01-07T10:30:00Z"
}
```

**Response:**
```json
{
  "message_id": "uuid-here",
  "status": "queued"
}
```

### POST /commands/{device_id}
Verstuur commando naar device

**Request:**
```json
{
  "command": "update_interval",
  "parameters": {
    "interval_seconds": 60
  }
}
```

### GET /devices/{device_id}/status
Haal device status op

**Response:**
```json
{
  "device_id": "sensor-001",
  "status": "online",
  "last_seen": "2026-01-07T10:30:00Z",
  "message_count_today": 1440,
  "rate_limit_remaining": 560
}
```

## Database Schema (DynamoDB)

**Table:** devices

| Attribute | Type | Description |
|-----------|------|-------------|
| device_id (PK) | String | Device identificatie |
| device_type | String | Type sensor/actuator |
| api_key_hash | String | Hashed API key |
| status | String | online/offline/suspended |
| metadata | Map | Device metadata |
| registered_at | String | ISO 8601 timestamp |
| last_seen | String | ISO 8601 timestamp |

**Table:** messages

| Attribute | Type | Description |
|-----------|------|-------------|
| message_id (PK) | String | UUID |
| device_id | String | Device identificatie |
| timestamp (SK) | String | ISO 8601 timestamp |
| payload | Map | Message data |
| status | String | queued/processed/failed |

**Table:** rate_limits

| Attribute | Type | Description |
|-----------|------|-------------|
| device_id (PK) | String | Device identificatie |
| window (SK) | String | Time window (hourly) |
| request_count | Number | Aantal requests |
| limit | Number | Max toegestaan |

## Architectuur

```
API Gateway (JWT Auth) → Lambda (Message Handler) → SQS
                                                      ↓
                                                Lambda (Processor)
                                                      ↓
                                               DynamoDB (messages)

API Gateway → Lambda (Device Mgmt) → DynamoDB (devices)
                                   ↓
                             Lambda (Rate Limiter) → DynamoDB (rate_limits)
```

## Security Features

- **Authentication:** JWT tokens via AWS Cognito
- **Rate Limiting:** Per-device request limits
- **Input Validation:** Schema validation voor alle payloads
- **Encryption:** TLS in transit, encryption at rest
- **API Keys:** Secure key generation en hashing

## Installatie & Gebruik

```bash
cd backend/project3-iot-gateway

# Build Docker image
docker build -t iot-gateway .

# Run lokaal
docker run -p 8000:8000 iot-gateway

# Deploy naar AWS
./deploy.sh
```

## Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Security tests
pytest tests/security/

# Load testing
locust -f tests/load/locustfile.py
```

## Rate Limiting

- **Free tier:** 1000 requests/hour per device
- **Standard tier:** 10000 requests/hour per device
- **Burst:** Max 100 requests/minute

Configureerbaar per device type.

---

## Load Testing (locust)

Rate limiting is alleen geloofwaardig als je het kunt bewijzen. Loadtesting met locust toont aan dat:
- Device X geblokkeerd wordt na X requests/minuut (429 Too Many Requests)
- Andere devices niet geraakt worden door het gedrag van één device
- De gateway stabiel blijft onder burst traffic

### Scenario's

1. **Normal load** — 10 devices, elk 1 request/seconde → alles 200
2. **Rate limit hit** — 1 device stuurt 200 requests/minuut → 429 na de drempel
3. **Burst isolation** — 1 device bombarded, 9 andere ongestoord → bewijst per-device isolatie

Dit is het sterkste argument voor loadtesting in project 3 — niet performance, maar correctheid van de rate limiting logica.
