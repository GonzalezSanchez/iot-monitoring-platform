# Project 3 — IoT Device Gateway

Secure gateway for IoT device registration, authentication, and message delivery.
Simulates the device layer of a production IoT platform — how physical sensors
authenticate and send data securely before it reaches the ingestion layer (Project 1).

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

**Async als ontwerpprincipe (3b).** De gateway wordt vanaf dag één async gebouwd (`async def`
routes + async I/O). Motivatie: een IoT-gateway is hét async-usecase — veel devices die
tegelijk verbinden en veel gelijktijdige kleine requests (I/O-bound). Dit staat bewust in
contrast met project 1b, dat sync is gebleven: bij die load volstaat de threadpool, en de
herschrijving zou geen functionele winst opleveren. Bij de gateway zit de concurrency wél
in het probleemdomein. (Project 4 gebruikt async om een andere reden: trage LLM I/O,
parallelle tool calls en streaming — zie `project4-llm-mcp.md`.)

---

## Tech Stack

- **Runtime:** Python 3.12
- **Cloud Services:** AWS API Gateway, Lambda, Cognito, DynamoDB, SQS
- **Containerization:** Docker
- **Testing:** pytest

## Architecture

```
IoT Device (sensor)
        │
        ▼
API Gateway (HTTP) — JWT auth via Cognito authorizer
        │
        ├── POST /devices/register     → RegisterDevice Lambda
        ├── POST /devices/{id}/auth    → AuthDevice Lambda (issues JWT)
        ├── POST /messages             → IngestMessage Lambda → SQS → ProcessMessage Lambda
        ├── POST /commands/{id}        → SendCommand Lambda → SQS (command queue)
        └── GET  /devices/{id}/status  → GetDeviceStatus Lambda
                │
                ▼
          DynamoDB
          ├── Devices table
          ├── Messages table
          └── RateLimits table
```

## Key Design Decisions

**Cognito for JWT** — device authentication uses AWS Cognito User Pools. Devices
register once, receive credentials, and exchange them for short-lived JWTs. API
Gateway validates the JWT on every request via a Cognito authorizer — no custom
auth logic in Lambda.

**SQS for reliable delivery** — messages are queued in SQS before processing.
If the processor Lambda fails, the message stays in the queue and retries automatically.
After max retries, messages go to a Dead Letter Queue (DLQ) for inspection.

**Rate limiting via DynamoDB** — per-device request counts are tracked in a
`RateLimits` table with a TTL-based sliding window. Checked in the IngestMessage
Lambda before queuing.

**Deploy/destroy strategy** — same as project 2a. Deploy for demos, destroy after
to minimise costs.

## API Endpoints

### POST /devices/register
Register a new IoT device. Returns an API key for subsequent authentication.

```json
// Request
{
  "device_id": "sensor-001",
  "device_type": "temperature_sensor",
  "metadata": { "location": "conference-a1", "model": "DHT22" }
}

// Response 201
{
  "device_id": "sensor-001",
  "api_key": "p3-xxxxxxxxxxxxxxxx",
  "status": "registered"
}
```

### POST /devices/{device_id}/auth
Exchange API key for a short-lived JWT (1 hour).

```json
// Request
{ "api_key": "p3-xxxxxxxxxxxxxxxx" }

// Response 200
{ "access_token": "eyJ...", "expires_in": 3600, "token_type": "Bearer" }
```

### POST /messages
Send a sensor reading. Requires `Authorization: Bearer <token>`.

```json
// Request
{
  "device_id": "sensor-001",
  "payload": { "temperature": 22.5, "humidity": 45 },
  "timestamp": "2026-01-07T10:30:00Z"
}

// Response 202
{ "message_id": "uuid", "status": "queued" }
```

### POST /commands/{device_id}
Send a command to a device (stored in command queue, polled by device).

```json
// Request
{ "command": "update_interval", "parameters": { "interval_seconds": 60 } }

// Response 202
{ "command_id": "uuid", "status": "queued" }
```

### GET /devices/{device_id}/status
Get current device status and rate limit info.

```json
// Response 200
{
  "device_id": "sensor-001",
  "status": "online",
  "last_seen": "2026-01-07T10:30:00Z",
  "message_count_today": 1440,
  "rate_limit_remaining": 560
}
```

## DynamoDB Schema

**Devices table** (`p3-{env}-Devices`):
- PK: `device_id` (String)
- Attributes: `device_type`, `api_key_hash`, `cognito_username`, `status` (registered/online/offline/suspended), `metadata` (Map), `registered_at`, `last_seen`

**Messages table** (`p3-{env}-Messages`):
- PK: `device_id` (String)
- SK: `timestamp` (String)
- Attributes: `message_id`, `payload` (Map), `status` (queued/processed/failed), `sqs_message_id`

**RateLimits table** (`p3-{env}-RateLimits`):
- PK: `device_id` (String)
- SK: `window` (String — hourly bucket e.g. `2026-01-07T10`)
- Attributes: `request_count` (Number), `limit` (Number), `ttl` (Number — epoch for DynamoDB TTL auto-cleanup)

## Infrastructure

Provisioned via CloudFormation in `infrastructure/`:

| File | What it creates |
|---|---|
| `cognito.yml` | Cognito User Pool + App Client for device auth |
| `dynamodb.yml` | Devices, Messages, RateLimits tables |
| `sqs.yml` | Message queue + Command queue + DLQs |
| `lambdas.yml` | 5 Lambda functions + IAM roles |
| `apigateway.yml` | HTTP API + Cognito authorizer + routes |

## Rate Limiting

- Default: 1000 messages/hour per device
- Configurable per device type in `config/rate_limits.yml`
- Sliding window tracked in DynamoDB RateLimits table with TTL auto-cleanup
- Exceeded limit → 429 Too Many Requests

## Security

- JWT validation via Cognito authorizer on API Gateway — no auth logic in Lambda
- API keys stored as bcrypt hashes in DynamoDB — never in plaintext
- Input validation via Pydantic on all Lambda handlers
- TLS in transit (API Gateway enforced), encryption at rest (DynamoDB default)
- Least-privilege IAM: each Lambda has its own role with only the permissions it needs

## Local Setup

```bash
cd backend/project3-iot-gateway

# Start LocalStack (DynamoDB + SQS + Cognito simulation)
docker-compose up -d

# Install dependencies
pip install -r requirements-dev.txt

# Run unit tests (moto — no Docker needed)
pytest tests/unit/ -v

# Run integration tests (requires LocalStack)
pytest tests/integration/ -v
```

## Deployment

```bash
# Deploy all stacks in order
./scripts/deploy.sh prod

# Tear down after demo
./scripts/destroy.sh prod
```

## Project Structure

```
project3-iot-gateway/
├── src/
│   ├── handlers/          # Lambda entry points
│   │   ├── register_device.py
│   │   ├── auth_device.py
│   │   ├── ingest_message.py
│   │   ├── process_message.py
│   │   ├── send_command.py
│   │   └── get_device_status.py
│   ├── models/            # Pydantic models
│   ├── repositories/      # DynamoDB access
│   ├── services/          # Business logic (auth, rate limiting)
│   └── utils/             # Response helpers
├── infrastructure/
│   ├── cognito.yml
│   ├── dynamodb.yml
│   ├── sqs.yml
│   ├── lambdas.yml
│   └── apigateway.yml
├── scripts/
│   ├── deploy.sh
│   ├── destroy.sh
│   └── simulate_device.py  ← simulates a device registering and sending messages
├── tests/
│   ├── unit/
│   └── integration/
├── docker/
│   └── docker-compose.yml  ← LocalStack
├── config/
│   └── rate_limits.yml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

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
