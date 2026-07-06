# Project 3 — IoT Device Gateway

Secure gateway for IoT device registration, authentication, and message delivery.
Simulates the device layer of a production IoT platform — how physical sensors
authenticate and send data securely before it reaches the ingestion layer (Project 1).

Secure gateway for IoT devices with authentication, rate limiting, and message queuing. Simulates a production-ready IoT platform with device management.

## Implementation Variants

Like project 1/1b and 2a/2b, project 3 is built in two variants — same security concept, different infrastructure:

| | AWS variant (3a) | FastAPI variant (3b) |
|---|---|---|
| Device auth | Cognito + API Gateway authorizer | Custom API keys — hashed in DynamoDB, validated via FastAPI `Depends()` |
| JWT | Issued by Cognito | `python-jose` — implemented in-house |
| Message queue | SQS | Kafka — Redpanda broker, `aiokafka` producer/consumer |
| Rate limiting | API Gateway built-in | Custom middleware in FastAPI |

**Chosen approach for 3b:** option 1 — API keys per device. A device registers, receives a generated key, and every request is validated via `Depends()`. Demonstrates security thinking (hashing, least privilege, rate limiting) without a full auth server. Fits the portfolio philosophy: don't overengineer, but demonstrate the principle.

**Async as a design principle (3b).** The gateway is built async from day one (`async def`
routes + async I/O). Rationale: an IoT gateway is the async use case par excellence — many devices
connecting at once and lots of concurrent small requests (I/O-bound). This deliberately
contrasts with project 1b, which stayed sync: at that load the threadpool is sufficient, and
rewriting it wouldn't yield any functional gain. In the gateway, though, the concurrency really
is inherent to the problem domain. (Project 4 uses async for a different reason: slow LLM I/O,
parallel tool calls, and streaming — see `project4-llm-mcp.md`.)

**Kafka as the 3b message queue (decided 2026-07-04).** The queue slot in 3b is filled by
Kafka rather than Redis or a DB-backed queue:

- **Why Kafka:** it is the mirror of SQS in 3a — same role (decouple ingestion from
  processing, absorb bursts, survive consumer failures) but with the semantics that matter
  in data engineering: an append-only log with offsets, replayable by design, consumer
  groups for parallelism, and a `device_id` partition key that guarantees per-device
  ordering. It also completes the platform story: batch (Airflow, 2b), lakehouse
  (Databricks, 2c), and now streaming.
- **Why Redpanda as the broker:** Kafka-API-compatible, a single container, no JVM and no
  ZooKeeper — light enough to run permanently on acer-server next to the existing stack.
  The application code uses the plain Kafka protocol (`aiokafka`), so nothing is
  Redpanda-specific; the broker could be swapped for Apache Kafka or MSK unchanged.
- **Why `aiokafka`:** async producer/consumer matches the async-first design of the
  gateway (see above) — publishing to Kafka inside an `async def` route without blocking
  the event loop.
- **Flow:** gateway authenticates + validates a device message, produces it to the
  `sensor-events` topic (key = `device_id`), and returns `202 queued`. A separate consumer
  service (own container, consumer group `gateway-normalizer`) reads the topic, normalises
  the payload to the shared `prod-SensorEvents` contract, and writes to DynamoDB. This is
  exactly the "project 3 owns the data contract" role described in the root README: after
  3b, projects 1b and 2a consume one consistent format.
- **Topics:** `sensor-events` (device → platform) and `device-commands` (platform →
  device, polled by the simulator) — mirroring the two SQS queues in 3a.
- **DLQ pattern:** messages that fail normalisation are produced to
  `sensor-events.dlq` with the error attached — the Kafka equivalent of the SQS DLQ in 3a,
  and the same never-lose-data philosophy as the 2c quarantine table.

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

### Architecture (3b — FastAPI + Kafka)

Same endpoints and security model, self-hosted infrastructure:

```
simulate_device.py (N devices)
        │  API key → JWT
        ▼
Gateway (FastAPI, async) — auth, validation, rate limiting
        │  produce (key = device_id)
        ▼
Redpanda broker ── topic sensor-events ──► consumer service (aiokafka,
        │                                  group gateway-normalizer)
        │                                        │ normalise to shared contract
        │                                        ▼
        │                                  DynamoDB prod-SensorEvents
        └── topic sensor-events.dlq  ◄── records that fail normalisation
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
cd backend/project3b-iot-gateway

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
project3b-iot-gateway/
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

Configurable per device type.

---

## Load Testing (locust)

Rate limiting is only credible if you can prove it. Load testing with locust demonstrates that:
- Device X gets blocked after X requests/minute (429 Too Many Requests)
- Other devices are unaffected by one device's behavior
- The gateway stays stable under burst traffic

### Scenarios

1. **Normal load** — 10 devices, each 1 request/second → all 200
2. **Rate limit hit** — 1 device sends 200 requests/minute → 429 past the threshold
3. **Burst isolation** — 1 device bombarded, 9 others unaffected → proves per-device isolation

This is the strongest argument for load testing in project 3 — not performance, but correctness of the rate limiting logic.
